import pytest

from fakes import FakeEmbedder
from knowledge_agent.index.embed import Embedder


def test_fake_embedder_is_deterministic_with_the_declared_dimension():
    embedder: Embedder = FakeEmbedder()

    first, second, other = embedder.embed(["same text", "same text", "other text"])

    assert len(first) == embedder.dimension
    assert first == second
    assert first != other


@pytest.mark.integration
def test_real_tokenizer_counts_past_the_model_limit_without_breaking_embedding():
    from knowledge_agent.index.embed import FastEmbedEmbedder

    embedder = FastEmbedEmbedder()
    text = " ".join(["word"] * 1000)

    assert embedder.count_tokens(text) > 512
    [vector] = embedder.embed([text])
    assert len(vector) == embedder.dimension == 384
