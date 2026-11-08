import pytest
from qdrant_client import QdrantClient

from fakes import FakeConnector, FakeEmbedder, by_paragraph, document
from knowledge_agent.index.search import search
from knowledge_agent.index.store import ChunkStore


@pytest.fixture
def store():
    store = ChunkStore(QdrantClient(":memory:"), FakeEmbedder())
    store.sync(
        FakeConnector("a", [document("a", "p1", "alpha", "beta"), document("a", "p2", "gamma")]),
        by_paragraph,
    )
    store.sync(
        FakeConnector(
            "b",
            [
                document("b", "q1", "delta"),
                document("b", "q2", "epsilon", access=("internal",)),
            ],
        ),
        by_paragraph,
    )
    return store


def test_exact_text_ranks_first_and_top_k_limits(store):
    results = search(store, "beta", top_k=2)

    assert results[0][0].text == "beta"
    assert results[0][1] == pytest.approx(1.0)
    assert len(results) == 2


def test_source_filter(store):
    assert {chunk.source for chunk, _ in search(store, "delta", top_k=10, source="a")} == {"a"}


def test_non_public_chunks_are_never_returned(store):
    texts = [chunk.text for chunk, _ in search(store, "epsilon", top_k=10)]

    assert "epsilon" not in texts
    assert "delta" in texts


def test_results_are_full_chunks_with_metadata(store):
    [(chunk, _)] = search(store, "gamma", top_k=1)

    assert chunk == by_paragraph(document("a", "p2", "gamma"))[0]
