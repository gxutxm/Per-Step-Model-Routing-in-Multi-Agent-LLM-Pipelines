"""Price table and cost calculation.

Prices are US dollars per 1 million tokens. The Gemini prices are the
standard paid-tier rates from https://ai.google.dev/gemini-api/docs/pricing
(output price includes thinking tokens). Qwen runs on our own GPU, so its
per-token price is 0.
"""

PRICING_PER_1M = {
    "flash": {"input": 1.50, "output": 9.00},
    "flash-lite": {"input": 0.30, "output": 2.50},
    "qwen": {"input": 0.0, "output": 0.0},
}


def compute_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Return the cost in US dollars of one call."""
    if model not in PRICING_PER_1M:
        raise KeyError(f"No price for model {model!r}. Add it to PRICING_PER_1M.")
    price = PRICING_PER_1M[model]
    return (tokens_in * price["input"] + tokens_out * price["output"]) / 1_000_000