import uuid
from datetime import datetime, timezone

import pytest
from qdrant_client import QdrantClient

from fakes import FakeEmbedder
from knowledge_agent.connectors.base import Connector, Document
from knowledge_agent.index.store import ChunkStore, EmptyFetchError, SyncReport
from knowledge_agent.ingestion.chunk import Chunk


class FakeConnector(Connector):
    def __init__(self, name: str, documents: list[Document], fail_after: int | None = None):
        self.name = name
        self.documents = documents
        self.fail_after = fail_after

    def fetch(self):
        for i, document in enumerate(self.documents):
            if i == self.fail_after:
                raise RuntimeError("source went down")
            yield document


def document(source: str, name: str, *paragraphs: str, version: str = "v1") -> Document:
    return Document(
        id=f"{source}:{name}",
        title=name,
        source=source,
        content="\n\n".join(paragraphs),
        uri=f"https://example.org/{name}",
        content_type="text/plain",
        version=version,
        fetched_at=datetime(2026, 10, 24, tzinfo=timezone.utc),
    )


def by_paragraph(document: Document) -> list[Chunk]:
    return [
        Chunk(
            id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document.source}\n{document.id}\n{text}")),
            document_id=document.id,
            source=document.source,
            text=text,
            heading_path=(document.title,),
            uri=document.uri,
            version=document.version,
            access=document.access,
            token_count=len(text.split()),
        )
        for text in document.content.split("\n\n")
    ]


P1 = document("a", "p1", "alpha", "beta")
P2 = document("a", "p2", "gamma")


@pytest.fixture
def store():
    return ChunkStore(QdrantClient(":memory:"), FakeEmbedder())


def sync(store, documents, source="a", **kwargs) -> SyncReport:
    return store.sync(FakeConnector(source, documents), by_paragraph, **kwargs)


def stored(store, source="a") -> dict[str, dict]:
    points, _ = store.client.scroll(store.collection, limit=1000, with_payload=True)
    return {p.payload["text"]: p.payload for p in points if p.payload["source"] == source}


def test_first_sync_adds_everything_and_second_sync_changes_nothing(store):
    assert sync(store, [P1, P2]) == SyncReport(documents=2, added=3)
    assert sync(store, [P1, P2]) == SyncReport(documents=2, skipped_documents=2, unchanged=3)
    assert stored(store).keys() == {"alpha", "beta", "gamma"}


def test_chunks_round_trip_through_the_payload(store):
    sync(store, [P1, P2])

    assert sorted(store.chunks("a"), key=lambda c: c.text) == sorted(
        by_paragraph(P1) + by_paragraph(P2), key=lambda c: c.text
    )


def test_edited_paragraph_replaces_only_its_chunk(store):
    sync(store, [P1, P2])

    report = sync(store, [document("a", "p1", "alpha", "BETA"), P2])

    assert report == SyncReport(
        documents=2, skipped_documents=1, added=1, unchanged=2, deleted=1
    )
    assert stored(store).keys() == {"alpha", "BETA", "gamma"}


def test_kept_chunks_get_new_payload_and_next_sync_skips(store):
    sync(store, [P1, P2])
    edited = document("a", "p1", "alpha", "BETA", version="v2")

    sync(store, [edited, P2])

    assert stored(store)["alpha"]["version"] == "v2"
    assert sync(store, [edited, P2]).skipped_documents == 2


def test_full_sync_rechunks_but_adds_nothing_when_unchanged(store):
    sync(store, [P1, P2])

    assert sync(store, [P1, P2], full=True) == SyncReport(documents=2, unchanged=3)


def test_disappeared_document_is_deleted(store):
    sync(store, [P1, P2])

    assert sync(store, [P1]) == SyncReport(documents=1, skipped_documents=1, unchanged=2, deleted=1)
    assert stored(store).keys() == {"alpha", "beta"}


def test_fetch_failing_midway_deletes_nothing(store):
    sync(store, [P1, P2])

    with pytest.raises(RuntimeError, match="source went down"):
        store.sync(FakeConnector("a", [P1, P2], fail_after=1), by_paragraph)

    assert stored(store).keys() == {"alpha", "beta", "gamma"}


def test_sync_of_one_source_leaves_other_sources_untouched(store):
    sync(store, [P1, P2])
    sync(store, [document("b", "q1", "delta"), document("b", "q2", "epsilon")], source="b")
    before = stored(store, "b")

    report = sync(store, [P1])

    assert report.deleted == 1
    assert stored(store).keys() == {"alpha", "beta"}
    assert stored(store, "b") == before


def test_empty_fetch_raises_and_deletes_nothing(store):
    sync(store, [P1, P2])

    with pytest.raises(EmptyFetchError, match="allow_empty=True"):
        sync(store, [])

    assert stored(store).keys() == {"alpha", "beta", "gamma"}


def test_empty_fetch_with_allow_empty_deletes_the_source(store):
    sync(store, [P1, P2])

    assert sync(store, [], allow_empty=True) == SyncReport(deleted=3)
    assert stored(store) == {}


def test_document_from_another_source_is_rejected(store):
    with pytest.raises(ValueError, match="expected 'a'"):
        sync(store, [document("b", "q1", "delta")])


def test_mixed_checksums_after_interrupted_sync_redo_the_document(store):
    sync(store, [P1, P2])
    store.client.set_payload(
        store.collection, {"document_checksum": "stale"}, points=[by_paragraph(P1)[0].id]
    )

    assert sync(store, [P1, P2]).skipped_documents == 1
    assert sync(store, [P1, P2]).skipped_documents == 2
