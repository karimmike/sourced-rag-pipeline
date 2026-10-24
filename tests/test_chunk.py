import uuid
from datetime import datetime, timezone

from knowledge_agent.connectors.base import Document
from knowledge_agent.ingestion.chunk import chunk_document
from knowledge_agent.ingestion.parse_html import Section

DOCUMENT = Document(
    id="erasmus_guide:/page",
    title="Guide page",
    source="test",
    content="<html></html>",
    uri="https://example.org/page",
    content_type="text/html",
    version="2026 v1, 12.11.2025",
    fetched_at=datetime(2026, 10, 22, tzinfo=timezone.utc),
    metadata={"pdf_url": "https://example.org/guide.pdf"},
)
HEADER = "Guide page > Funding rules > Travel support"  # 8 "tokens" for count_words


def count_words(text: str) -> int:
    return len(text.split())


def make_section(text: str, footnotes: dict[str, str] | None = None) -> Section:
    return Section(
        heading_path=("Guide page", "Funding rules", "Travel support"),
        text=text,
        slug="funding-rules/travel-support",
        fragment="#:~:text=Travel%20support",
        footnotes=footnotes or {},
    )


def words(label: str, n: int) -> str:
    return " ".join([label] + ["word"] * n)


def test_small_section_is_one_chunk_with_metadata():
    [chunk] = chunk_document(DOCUMENT, [make_section("Short paragraph.")], count_words)

    assert chunk.text == f"{HEADER}\n\nShort paragraph."
    assert chunk.document_id == DOCUMENT.id
    assert chunk.source == "test"
    assert chunk.heading_path == ("Guide page", "Funding rules", "Travel support")
    assert chunk.uri == "https://example.org/page#:~:text=Travel%20support"
    assert chunk.version == "2026 v1, 12.11.2025"
    assert chunk.access == ("public",)
    assert chunk.metadata == {"pdf_url": "https://example.org/guide.pdf"}
    assert chunk.token_count == 10


def test_long_section_splits_on_paragraphs_with_heading_on_each_piece():
    paragraphs = [words(f"P{i}", 20) for i in range(10)]  # 21 words each

    chunks = chunk_document(
        DOCUMENT, [make_section("\n\n".join(paragraphs))], count_words, max_tokens=60
    )

    # 8 (header) + 2 * 21 = 50 fits; a third paragraph would make 71.
    assert len(chunks) == 5
    assert all(c.text.startswith(HEADER + "\n\n") for c in chunks)
    assert all(c.token_count <= 60 for c in chunks)
    bodies = [c.text.removeprefix(HEADER + "\n\n") for c in chunks]
    assert "\n\n".join(bodies) == "\n\n".join(paragraphs)  # nothing lost or cut


def test_footnote_goes_with_the_piece_that_references_it():
    section = make_section(
        "See the venue[17] of the activity.\n\n" + words("Filler", 30),
        footnotes={"17": "For example Madrid to Rome."},
    )

    first, second = chunk_document(DOCUMENT, [section], count_words, max_tokens=40)

    assert first.text.endswith("[17] For example Madrid to Rome.")
    assert "Madrid" not in second.text


def test_paragraph_over_the_limit_becomes_its_own_chunk():
    [chunk] = chunk_document(DOCUMENT, [make_section(words("Long", 99))], count_words, max_tokens=50)

    assert chunk.token_count == 108


def test_chunk_id_is_a_stable_uuid():
    [a] = chunk_document(DOCUMENT, [make_section("Same text.")], count_words)
    [b] = chunk_document(DOCUMENT, [make_section("Same text.")], count_words)
    [c] = chunk_document(DOCUMENT, [make_section("Other text.")], count_words)

    assert a.id == b.id
    assert a.id != c.id
    uuid.UUID(a.id)  # raises if not a valid UUID
