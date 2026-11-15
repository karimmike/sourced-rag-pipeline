"""Model prices for cost estimates. Update by hand when Anthropic's prices change."""

# USD per million tokens (input, output), Anthropic API.
# Source: Anthropic model pricing, as of 2026-11-03.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),  # prompts up to 100K tokens; higher above that
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-fable-5-2": (8.00, 40.00),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimated cost in USD, or None for a model without a listed price."""
    if model not in PRICES_PER_MTOK:
        return None
    input_price, output_price = PRICES_PER_MTOK[model]
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
