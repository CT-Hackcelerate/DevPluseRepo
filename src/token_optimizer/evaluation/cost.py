"""Cost model — tokens × per-model price.

Prices ($ per 1M tokens) mirror ``llm.client._PRICING`` so eval numbers match
the live client's estimates. Kept here too so the eval harness runs fully
offline without importing the Anthropic SDK.
"""

from __future__ import annotations

# ($ per 1M tokens) → (input_rate, output_rate)
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

_DEFAULT_RATE = (5.0, 25.0)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return the estimated USD cost for a call at ``model``'s list price."""
    in_rate, out_rate = PRICING.get(model, _DEFAULT_RATE)
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000
