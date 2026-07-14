"""Text optimization pipeline — shrink a document's text before the model sees it.

Where ``OptimizedRunner`` takes structured JIRA/DevOps items, this pipeline takes
free-form document text (from ``integrations.document.read_document``) and applies
the deterministic strategies — prose compression, then optional Haiku
summarization — reporting exactly how many tokens were saved.

Token counting uses the API's ``count_tokens`` endpoint when an API key is
configured, and falls back to a local estimate otherwise, so the pipeline works
fully offline (compression only).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..config import Config
from ..llm.cache import ResponseCache
from ..llm.client import ClaudeClient
from .compress import compress_prose
from .summarize import _SUMMARY_SYSTEM
from .tokens import estimate_tokens


@dataclass
class TextOptimizationResult:
    raw_text: str
    optimized_text: str
    raw_tokens: int
    optimized_tokens: int
    token_method: str  # "api" (count_tokens) or "estimate" (local heuristic)
    stages: list[str] = field(default_factory=list)
    estimated_cost_usd: float = 0.0

    @property
    def tokens_saved(self) -> int:
        return max(0, self.raw_tokens - self.optimized_tokens)

    @property
    def reduction_pct(self) -> float:
        if self.raw_tokens == 0:
            return 0.0
        return 100.0 * self.tokens_saved / self.raw_tokens

    def summary(self) -> str:
        method = "API count_tokens" if self.token_method == "api" else "local estimate"
        return (
            f"raw={self.raw_tokens} tok  ->  optimized={self.optimized_tokens} tok  "
            f"(saved {self.tokens_saved} tok, {self.reduction_pct:.1f}% smaller)  "
            f"| stages: {', '.join(self.stages) or 'none'}  "
            f"| tokens counted via {method}"
        )


@dataclass
class TextOptimizer:
    """Optimize free-form document text and report the token savings."""

    config: Config
    client: Optional[ClaudeClient] = field(init=False, default=None)

    def __post_init__(self) -> None:
        # A client (and API key) is only required for summarization / API-accurate
        # token counting. Compression works offline, so we don't hard-require it.
        if self.config.anthropic_api_key:
            cache = ResponseCache(self.config.cache_dir)
            self.client = ClaudeClient(
                api_key=self.config.anthropic_api_key,
                model=self.config.model,
                cache=cache,
            )

    def _count(self, text: str) -> int:
        if self.client is not None:
            try:
                return self.client.count_tokens(
                    messages=[{"role": "user", "content": text}]
                )
            except Exception:
                # Network/API hiccup — degrade gracefully to the local estimate.
                pass
        return estimate_tokens(text)

    def optimize(
        self,
        text: str,
        *,
        summarize: bool = False,
        max_chars: int = 24000,
    ) -> TextOptimizationResult:
        """Run the optimization strategies over ``text``.

        With ``summarize=True`` (requires an API key), a cheap Haiku pass rewrites
        the compressed text into a dense, agent-ready summary — the biggest single
        saving on long documents.
        """
        stages: list[str] = []
        raw_tokens = self._count(text)

        # Strategy 2 — deterministic prose compression (always, offline).
        optimized = compress_prose(text, max_chars=max_chars)
        if optimized != text:
            stages.append("compress")

        # Strategy 3 — smart summarization (optional, needs the model).
        if summarize:
            if self.client is None:
                raise RuntimeError(
                    "Summarization needs an ANTHROPIC_API_KEY. Set it in your "
                    "environment or .env, or turn summarization off to compress only."
                )
            optimized = self.client.complete(
                system=_SUMMARY_SYSTEM,
                user=f"Summarize the following document for an AI agent:\n\n{optimized}",
                model=self.config.summary_model,
                max_tokens=2048,
                effort="low",
                adaptive_thinking=False,
            )
            stages.append("summarize")

        optimized_tokens = self._count(optimized)
        token_method = "api" if self.client is not None else "estimate"
        cost = self.client.estimate_cost() if self.client is not None else 0.0

        return TextOptimizationResult(
            raw_text=text,
            optimized_text=optimized,
            raw_tokens=raw_tokens,
            optimized_tokens=optimized_tokens,
            token_method=token_method,
            stages=stages,
            estimated_cost_usd=cost,
        )


def optimize_document(
    config: Config,
    path: str,
    *,
    summarize: bool = False,
) -> TextOptimizationResult:
    """Read a document from ``path`` and return its optimization result."""
    from ..integrations.document import read_document

    text = read_document(path)
    return TextOptimizer(config).optimize(text, summarize=summarize)


def write_output(result: TextOptimizationResult, path: str) -> None:
    """Write the optimized text (with a stats header) to ``path``."""
    header = (
        "=" * 70 + "\n"
        "TokenOptimizer — optimized document output\n"
        + "-" * 70 + "\n"
        + result.summary() + "\n"
        + "=" * 70 + "\n\n"
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header)
        fh.write(result.optimized_text)
        fh.write("\n")
