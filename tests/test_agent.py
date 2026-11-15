import pytest
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import UsageLimits
from qdrant_client import QdrantClient

from fakes import FakeConnector, FakeEmbedder, by_paragraph, document
from knowledge_agent.agent.answer import UNVERIFIED_ANSWER, ask
from knowledge_agent.config import settings
from knowledge_agent.index.store import ChunkStore


@pytest.fixture
def store():
    store = ChunkStore(QdrantClient(":memory:"), FakeEmbedder())
    store.sync(
        FakeConnector(
            "guide",
            [document("guide", "ka1", "Students receive 900 EUR per month.", "Staff get travel support.")],
        ),
        by_paragraph,
    )
    return store


def scripted(*steps):
    """A model that plays the given steps in order, one per request."""
    remaining = list(steps)
    return FunctionModel(lambda messages, info: remaining.pop(0)(messages, info))


def last_search_result(messages):
    for message in reversed(messages):
        for part in message.parts:
            if isinstance(part, ToolReturnPart) and part.tool_name == "search_guide":
                return part.content
    return None


def final(info, *citations, enough_evidence=True):
    args = {"answer": "An answer.", "citations": list(citations), "enough_evidence": enough_evidence}
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])


def do_search(messages, info):
    return ModelResponse(parts=[ToolCallPart("search_guide", {"query": "student grant"})])


def cite_first(messages, info):
    chunk = last_search_result(messages)[0]
    return final(info, {"chunk_id": chunk["chunk_id"], "quote": chunk["text"]})


def cite_unknown(messages, info):
    return final(info, {"chunk_id": "never-retrieved", "quote": "900 EUR"})


def abstain(messages, info):
    return final(info, enough_evidence=False)


def test_grounded_answer_with_stats(store):
    result = ask("What do students receive?", store, model=scripted(do_search, cite_first))

    assert result.answer.enough_evidence
    [source] = result.answer.sources
    assert source.source == "guide"
    assert source.uri == "https://example.org/ka1"
    assert result.stats.searches == 1
    assert result.stats.input_tokens > 0 and result.stats.output_tokens > 0
    assert result.stats.elapsed_seconds >= 0


def test_bad_citation_is_retried_and_fixed(store):
    result = ask("What do students receive?", store, model=scripted(do_search, cite_unknown, cite_first))
    assert result.answer.enough_evidence


def test_citation_failing_after_retry_abstains(store):
    result = ask("What do students receive?", store, model=scripted(do_search, cite_unknown, cite_unknown))

    assert not result.answer.enough_evidence
    assert result.answer.abstain_reason == "citation_check_failed"
    assert result.answer.answer == UNVERIFIED_ANSWER
    assert result.answer.sources == []
    assert result.stats.input_tokens > 0


def test_model_abstention_is_insufficient_evidence(store):
    result = ask("What is the grant on Mars?", store, model=scripted(do_search, abstain))
    assert result.answer.abstain_reason == "insufficient_evidence"


def test_search_limit_stops_further_searches(store, monkeypatch):
    monkeypatch.setattr(settings, "max_searches", 1)
    seen = []

    def abstain_after_limit(messages, info):
        seen.append(last_search_result(messages))
        return abstain(messages, info)

    result = ask("Q", store, model=scripted(do_search, do_search, abstain_after_limit))

    assert result.stats.searches == 1
    assert "Search limit reached" in seen[0]
    assert result.answer.abstain_reason == "insufficient_evidence"


def test_usage_limit_raises_and_is_not_an_abstention(store, monkeypatch):
    monkeypatch.setattr("knowledge_agent.agent.answer.USAGE_LIMITS", UsageLimits(request_limit=2))
    with pytest.raises(UsageLimitExceeded):
        ask("Q", store, model=scripted(do_search, do_search, do_search, abstain))
