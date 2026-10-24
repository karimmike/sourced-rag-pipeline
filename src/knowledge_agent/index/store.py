"""Chunks of all sources in one Qdrant collection, with incremental sync per source."""

from collections.abc import Callable, Iterable, Iterator

from pydantic import BaseModel
from qdrant_client import QdrantClient, models

from knowledge_agent.connectors.base import Connector, Document
from knowledge_agent.index.embed import Embedder
from knowledge_agent.ingestion.chunk import Chunk

SCROLL_PAGE = 256


class SyncReport(BaseModel):
    """What one sync of one source changed, counted in chunks unless named documents."""

    documents: int = 0
    skipped_documents: int = 0
    added: int = 0
    unchanged: int = 0
    deleted: int = 0


class EmptyFetchError(RuntimeError):
    """fetch() returned nothing while the index still holds documents for that source."""


def collection_name(embedder: Embedder) -> str:
    """One collection per model: vectors from different models are not comparable."""
    return "sourced__" + embedder.model_name.split("/")[-1]


class ChunkStore:
    """Stores chunks as Qdrant points: id = chunk id, payload = chunk metadata."""

    def __init__(self, client: QdrantClient, embedder: Embedder):
        self.client = client
        self.embedder = embedder
        self.collection = collection_name(embedder)
        if not client.collection_exists(self.collection):
            client.create_collection(
                self.collection,
                models.VectorParams(size=embedder.dimension, distance=models.Distance.COSINE),
            )

    def sync(
        self,
        connector: Connector,
        chunk: Callable[[Document], list[Chunk]],
        full: bool = False,
        allow_empty: bool = False,
    ) -> SyncReport:
        """Make the index match the connector's documents, touching only its own source.

        full=True ignores the checksum shortcut, for when the chunker changed. An empty
        fetch raises EmptyFetchError instead of deleting the source, unless allow_empty=True.
        """
        source = connector.name
        indexed = self._indexed(source)
        fetched: set[str] = set()
        report = SyncReport()
        for document in connector.fetch():
            if document.source != source:
                raise ValueError(f"{document.id}: source {document.source!r}, expected {source!r}")
            report.documents += 1
            fetched.add(document.id)
            checksum, old_ids = indexed.get(document.id, (None, set()))
            if checksum == document.checksum and not full:
                report.skipped_documents += 1
                report.unchanged += len(old_ids)
                continue
            chunks = chunk(document)
            new = [c for c in chunks if c.id not in old_ids]
            kept = [c for c in chunks if c.id in old_ids]
            vanished = old_ids - {c.id for c in chunks}
            # This order leaves mixed checksums after a crash, so the next sync redoes the document.
            self._upsert(new, document.checksum)
            self._overwrite_payloads(kept, document.checksum)
            self._delete(source, vanished)
            report.added += len(new)
            report.unchanged += len(kept)
            report.deleted += len(vanished)
        # An empty fetch is more likely a broken source than a source that was emptied.
        if not fetched and indexed and not allow_empty:
            raise EmptyFetchError(
                f"{source}: fetch() returned no documents but the index holds {len(indexed)}; "
                "nothing deleted. Pass allow_empty=True to delete them."
            )
        # Reached only if fetch() completed; by its contract it raises on any failure.
        for document_id in indexed.keys() - fetched:
            _, ids = indexed[document_id]
            self._delete(source, ids)
            report.deleted += len(ids)
        return report

    def chunks(self, source: str) -> list[Chunk]:
        """All indexed chunks of one source, rebuilt from their payloads."""
        return [
            Chunk(id=str(point.id), **_without(point.payload, "document_checksum"))
            for point in self._scroll(source, with_payload=True)
        ]

    def _indexed(self, source: str) -> dict[str, tuple[str | None, set[str]]]:
        checksums: dict[str, set[str]] = {}
        ids: dict[str, set[str]] = {}
        for point in self._scroll(source, with_payload=["document_id", "document_checksum"]):
            document_id = point.payload["document_id"]
            checksums.setdefault(document_id, set()).add(point.payload["document_checksum"])
            ids.setdefault(document_id, set()).add(str(point.id))
        # A document whose points disagree on the checksum (interrupted sync) never matches.
        return {
            doc: (next(iter(sums)) if len(sums) == 1 else None, ids[doc])
            for doc, sums in checksums.items()
        }

    def _scroll(self, source: str, with_payload: bool | list[str]) -> Iterator[models.Record]:
        offset = None
        while True:
            points, offset = self.client.scroll(
                self.collection,
                scroll_filter=_source_filter(source),
                limit=SCROLL_PAGE,
                offset=offset,
                with_payload=with_payload,
            )
            yield from points
            if offset is None:
                return

    def _upsert(self, chunks: list[Chunk], checksum: str) -> None:
        if not chunks:
            return
        vectors = self.embedder.embed([c.text for c in chunks])
        self.client.upsert(
            self.collection,
            [
                models.PointStruct(id=c.id, vector=vector, payload=_payload(c, checksum))
                for c, vector in zip(chunks, vectors, strict=True)
            ],
        )

    def _overwrite_payloads(self, chunks: list[Chunk], checksum: str) -> None:
        # Same text, so no new embedding, but version or link may have changed.
        if not chunks:
            return
        self.client.batch_update_points(
            self.collection,
            [
                models.OverwritePayloadOperation(
                    overwrite_payload=models.SetPayload(payload=_payload(c, checksum), points=[c.id])
                )
                for c in chunks
            ],
        )

    def _delete(self, source: str, ids: Iterable[str]) -> None:
        ids = list(ids)
        if not ids:
            return
        # The source condition makes deleting another source's point impossible, even by id.
        self.client.delete(
            self.collection,
            models.FilterSelector(
                filter=models.Filter(
                    must=[*_source_filter(source).must, models.HasIdCondition(has_id=ids)]
                )
            ),
        )


def _source_filter(source: str) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key="source", match=models.MatchValue(value=source))]
    )


def _payload(chunk: Chunk, checksum: str) -> dict:
    return {**chunk.model_dump(mode="json", exclude={"id"}), "document_checksum": checksum}


def _without(payload: dict, key: str) -> dict:
    return {k: v for k, v in payload.items() if k != key}
