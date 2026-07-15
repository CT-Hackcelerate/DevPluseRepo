"""Thin wrapper over the Anthropic SDK with the token-saving features wired in.

Responsibilities:
  * native prompt caching via ``cache_control`` on the stable system prefix
  * adaptive thinking + effort control
  * local response cache (exact-match, 0-token hits)
  * accurate token accounting via the ``count_tokens`` endpoint (never tiktoken)
  * streaming for large ``max_tokens`` so we don't hit SDK HTTP timeouts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import anthropic

from .cache import ResponseCache


@dataclass
class Usage:
    """Running tally of tokens across a session, split by cache tier."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    local_cache_hits: int = 0

    def add(self, u: Any) -> None:
        self.input_tokens += getattr(u, "input_tokens", 0) or 0
        self.output_tokens += getattr(u, "output_tokens", 0) or 0
        self.cache_read_input_tokens += getattr(u, "cache_read_input_tokens", 0) or 0
        self.cache_creation_input_tokens += getattr(u, "cache_creation_input_tokens", 0) or 0

    @property
    def billable_input(self) -> int:
        """Tokens paid at full price (cache reads are ~0.1x, excluded here)."""
        return self.input_tokens

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "local_cache_hits": self.local_cache_hits,
        }


# Rough public list pricing ($ per 1M tokens) for cost estimates only.
_PRICING = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

# Models that accept output_config.effort. Haiku 4.5 and Sonnet 4.5 reject it
# with a 400, so we omit the parameter for anything not listed here.
_EFFORT_MODELS = (
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-opus-4-5",
    "claude-sonnet-5",
    "claude-sonnet-4-6",
    "claude-fable-5",
)


def _supports_effort(model: str) -> bool:
    return model in _EFFORT_MODELS


@dataclass
class ClaudeClient:
    api_key: str
    model: str = "claude-opus-4-8"
    cache: Optional[ResponseCache] = None
    usage: Usage = field(default_factory=Usage)
    _client: anthropic.Anthropic = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=self.api_key or None)

    # ── token accounting ────────────────────────────────────────────
    def count_tokens(
        self,
        messages: list[dict[str, Any]],
        system: Optional[str | list[dict[str, Any]]] = None,
        model: Optional[str] = None,
    ) -> int:
        """Accurate, model-specific token count for a prompt (no tiktoken)."""
        kwargs: dict[str, Any] = {"model": model or self.model, "messages": messages}
        if system:
            kwargs["system"] = system
        resp = self._client.messages.count_tokens(**kwargs)
        return resp.input_tokens

    # ── generation ──────────────────────────────────────────────────
    def complete(
        self,
        *,
        system: str,
        user: str,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        effort: str = "high",
        adaptive_thinking: bool = True,
        cache_system: bool = True,
        use_local_cache: bool = True,
    ) -> str:
        """Run one turn against Claude, applying every caching layer.

        ``system`` is treated as the stable, cacheable prefix (a cache_control
        breakpoint is placed on it). Keep volatile content (timestamps, IDs) in
        ``user`` so the cached prefix stays byte-stable across calls.
        """
        model = model or self.model

        # System prompt as a cacheable block — this is the server-side cache.
        system_blocks: list[dict[str, Any]] = [{"type": "text", "text": system}]
        if cache_system:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        messages = [{"role": "user", "content": user}]

        request: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_blocks,
            "messages": messages,
        }
        # effort is rejected by Haiku 4.5 / Sonnet 4.5 — only send it when supported.
        if _supports_effort(model):
            request["output_config"] = {"effort": effort}
        if adaptive_thinking:
            request["thinking"] = {"type": "adaptive"}

        # Exact-match local cache: identical request → 0 tokens.
        if use_local_cache and self.cache is not None:
            hit = self.cache.get(request)
            if hit is not None:
                self.usage.local_cache_hits += 1
                return hit["text"]

        text = self._invoke(request)

        if use_local_cache and self.cache is not None:
            self.cache.set(request, {"text": text})
        return text

    def _invoke(self, request: dict[str, Any]) -> str:
        # Stream whenever max_tokens is large, to avoid SDK HTTP timeouts.
        if request.get("max_tokens", 0) > 16000:
            with self._client.messages.stream(**request) as stream:
                message = stream.get_final_message()
        else:
            message = self._client.messages.create(**request)

        self.usage.add(message.usage)

        if message.stop_reason == "refusal":
            return "[refused] The request was declined by safety classifiers."

        return "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        )

    # ── cost helper ─────────────────────────────────────────────────
    def estimate_cost(self, model: Optional[str] = None) -> float:
        model = model or self.model
        in_rate, out_rate = _PRICING.get(model, (5.0, 25.0))
        # Cache reads bill ~0.1x, writes ~1.25x.
        return (
            self.usage.input_tokens * in_rate
            + self.usage.cache_read_input_tokens * in_rate * 0.1
            + self.usage.cache_creation_input_tokens * in_rate * 1.25
            + self.usage.output_tokens * out_rate
        ) / 1_000_000
