"""Split sections into chunks that fit the embedding model, with metadata for citations."""

import uuid
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, Field

from knowledge_agent.connectors.base import Document
from knowledge_agent.ingestion.parse_html import Section

# bge-small-en-v1.5 reads at most 512 tokens and ignores the rest; we stay below that.
MAX_TOKENS = 400
# Fixed namespace, so the same chunk always gets the same id.
CHUNK_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/karimmike/sourced-rag-pipeline/chunk")


class Chunk(BaseModel):
    """A piece of a section: the unit we embed, retrieve and cite."""

    model_config = ConfigDict(frozen=True)

    id: str
    document_id: str
    source: str
    text: str
    heading_path: tuple[str, ...]
    uri: str
    version: str | None
    access: tuple[str, ...]
    token_count: int
    # Copied from the Document, e.g. {"pdf_url": ...}. Treat as read-only.
    metadata: dict[str, str] = Field(default_factory=dict)


def chunk_document(
    document: Document,
    sections: list[Section],
    count_tokens: Callable[[str], int],
    max_tokens: int = MAX_TOKENS,
) -> list[Chunk]:
    """One chunk per section; a section over max_tokens is split on paragraphs.

    Chunk ids depend only on source, document id, section slug and text, so sync can
    compare them across runs.
    """
    chunks = []
    for section in sections:
        header = " > ".join(section.heading_path)
        for blocks in _pack(header, section, count_tokens, max_tokens):
            text = _render(header, blocks, section.footnotes)
            # Newline-separated: sources, ids and slugs have no newlines, so the key is unambiguous.
            key = "\n".join([document.source, document.id, section.slug, text])
            chunks.append(
                Chunk(
                    id=str(uuid.uuid5(CHUNK_NAMESPACE, key)),
                    document_id=document.id,
                    source=document.source,
                    text=text,
                    heading_path=section.heading_path,
                    uri=document.uri + section.fragment,
                    version=document.version,
                    access=document.access,
                    token_count=count_tokens(text),
                    metadata=dict(document.metadata),
                )
            )
    return chunks


def _pack(
    header: str, section: Section, count_tokens: Callable[[str], int], max_tokens: int
) -> list[list[str]]:
    pieces: list[list[str]] = []
    current: list[str] = []
    for block in section.text.split("\n\n"):
        candidate = _render(header, current + [block], section.footnotes)
        if current and count_tokens(candidate) > max_tokens:
            pieces.append(current)
            current = []
        current.append(block)
    pieces.append(current)
    return pieces


def _render(header: str, blocks: list[str], footnotes: dict[str, str]) -> str:
    body = "\n\n".join(blocks)
    notes = [f"[{number}] {text}" for number, text in footnotes.items() if f"[{number}]" in body]
    return "\n\n".join([header, body, *notes])
