import pytest

from knowledge_agent.pricing import estimate_cost


def test_cost_uses_input_and_output_prices():
    assert estimate_cost("claude-sonnet-5-5", 1_000_000, 100_000) == pytest.approx(3.0)


def test_unknown_model_has_no_cost():
    assert estimate_cost("some-other-model", 1_000, 1_000) is None
