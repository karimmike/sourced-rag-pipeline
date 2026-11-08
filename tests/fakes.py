import hashlib
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from knowledge_agent.connectors.base import Connector, Document
from knowledge_agent.ingestion.chunk import Chunk


class FakeEmbedder:
    """Deterministic stand-in for FastEmbedEmbedder: no model, no network."""

    model_name = "fake-embedder"
    dimension = 8

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [
            [byte / 255 for byte in hashlib.sha256(text.encode("utf-8")).digest()[: self.dimension]]
            for text in texts
        ]

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def count_tokens(self, text: str) -> int:
        return len(text.split())


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


def document(
    source: str,
    name: str,
    *paragraphs: str,
    version: str = "v1",
    access: tuple[str, ...] = ("public",),
) -> Document:
    return Document(
        id=f"{source}:{name}",
        title=name,
        source=source,
        content="\n\n".join(paragraphs),
        uri=f"https://example.org/{name}",
        content_type="text/plain",
        version=version,
        fetched_at=datetime(2026, 10, 24, tzinfo=timezone.utc),
        access=access,
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
