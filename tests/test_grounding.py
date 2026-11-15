import pytest
from pydantic import ValidationError

from knowledge_agent.agent.grounding import CitationError, ground
from knowledge_agent.agent.schema import AgentAnswer, Citation
from knowledge_agent.ingestion.chunk import Chunk

CHUNK = Chunk(
    id="c1",
    document_id="erasmus:ka1",
    source="erasmus_guide",
    text="Students receive\na monthly grant of 900 EUR.",
    heading_path=("Part B", "KA1"),
    uri="https://example.org/ka1#grants",
    version="2026 v1",
    access=("public",),
    token_count=8,
)
RETRIEVED = {CHUNK.id: CHUNK}


def cited(*citations: Citation) -> AgentAnswer:
    return AgentAnswer(answer="900 EUR per month.", citations=list(citations), enough_evidence=True)


def test_valid_citation_takes_metadata_from_chunk():
    result = ground(cited(Citation(chunk_id="c1", quote="a monthly grant of 900 EUR")), RETRIEVED)

    assert result.enough_evidence and result.abstain_reason is None
    [source] = result.sources
    assert source.chunk_id == "c1"
    assert source.source == "erasmus_guide"
    assert source.heading_path == ("Part B", "KA1")
    assert source.uri == "https://example.org/ka1#grants"
    assert source.version == "2026 v1"


def test_unknown_chunk_id_fails():
    with pytest.raises(CitationError, match="not retrieved"):
        ground(cited(Citation(chunk_id="c9", quote="a monthly grant")), RETRIEVED)


def test_quote_not_in_chunk_fails():
    with pytest.raises(CitationError, match="not found"):
        ground(cited(Citation(chunk_id="c1", quote="a monthly grant of 1000 EUR")), RETRIEVED)


def test_quote_with_different_line_breaks_passes():
    result = ground(cited(Citation(chunk_id="c1", quote="Students receive a monthly\n  grant")), RETRIEVED)
    assert len(result.sources) == 1


def test_quote_differing_only_in_case_fails():
    with pytest.raises(CitationError, match="not found"):
        ground(cited(Citation(chunk_id="c1", quote="A Monthly Grant of 900 EUR")), RETRIEVED)


def test_empty_quote_fails():
    with pytest.raises(CitationError, match="empty"):
        ground(cited(Citation(chunk_id="c1", quote=" \n ")), RETRIEVED)


def test_every_bad_citation_is_reported():
    with pytest.raises(CitationError) as error:
        ground(
            cited(
                Citation(chunk_id="c9", quote="a monthly grant"),
                Citation(chunk_id="c1", quote="1000 EUR"),
            ),
            RETRIEVED,
        )
    assert len(error.value.problems) == 2
    assert "citation 1" in str(error.value) and "citation 2" in str(error.value)


def test_abstention_passes_with_insufficient_evidence():
    abstention = AgentAnswer(answer="The guide does not say.", citations=[], enough_evidence=False)
    result = ground(abstention, RETRIEVED)

    assert not result.enough_evidence
    assert result.sources == []
    assert result.abstain_reason == "insufficient_evidence"


def test_enough_evidence_requires_a_citation():
    with pytest.raises(ValidationError, match="requires at least one citation"):
        AgentAnswer(answer="900 EUR.", citations=[], enough_evidence=True)


def test_abstention_must_not_have_citations():
    with pytest.raises(ValidationError, match="must not have citations"):
        AgentAnswer(
            answer="Not sure.",
            citations=[Citation(chunk_id="c1", quote="900 EUR")],
            enough_evidence=False,
        )
