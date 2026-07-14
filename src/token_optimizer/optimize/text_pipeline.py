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
from .local import extractive_summary, reduce_text
from .local_model import get_local_summarizer
from .summarize import _SUMMARY_SYSTEM
from .tokens import count_tokens_offline

_TOKEN_METHOD_LABELS = {
    "api": "API count_tokens",
    "tiktoken": "local tiktoken (cl100k)",
    "estimate": "local estimate",
}


@dataclass
class TextOptimizationResult:
    raw_text: str
    optimized_text: str
    raw_tokens: int
    optimized_tokens: int
    token_method: str  # "api" | "tiktoken" | "estimate"
    stages: list[str] = field(default_factory=list)
    estimated_cost_usd: float = 0.0
    summary_tier: str = "none"  # "haiku" | "local-model" | "extractive" | "none"
    duration_ms: float = 0.0

    @property
    def tokens_saved(self) -> int:
        return max(0, self.raw_tokens - self.optimized_tokens)

    @property
    def reduction_pct(self) -> float:
        if self.raw_tokens == 0:
            return 0.0
        return 100.0 * self.tokens_saved / self.raw_tokens

    def summary(self) -> str:
        method = _TOKEN_METHOD_LABELS.get(self.token_method, self.token_method)
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
        # A client (and API key) is only required for LLM summarization / API-exact
        # token counting. Every other strategy works offline, so we don't require it.
        if self.config.anthropic_api_key:
            cache = ResponseCache(self.config.cache_dir)
            self.client = ClaudeClient(
                api_key=self.config.anthropic_api_key,
                model=self.config.model,
                cache=cache,
            )

    def _local_or_extractive(self, text: str, ratio: float, stages: list[str]) -> str:
        """No cloud key: try a local Ollama model (abstractive), else extractive.

        Records ``local-model-summarize`` or ``extractive-summarize`` in ``stages``
        depending on which tier actually ran and changed the text.
        """
        summarizer = get_local_summarizer(self.config.local_model, self.config.local_model_url)
        if summarizer is not None:
            out = summarizer.summarize(text)
            if out and out != text:
                stages.append("local-model-summarize")
                return out
            # Local model configured but produced nothing usable — fall through.
        summarized = extractive_summary(text, ratio=ratio)
        if summarized != text:
            stages.append("extractive-summarize")
        return summarized

    def _count(self, text: str) -> tuple[int, str]:
        """Return (token_count, method): API-exact if a key is set, else offline."""
        if self.client is not None:
            try:
                return (
                    self.client.count_tokens(messages=[{"role": "user", "content": text}]),
                    "api",
                )
            except Exception:
                # Network/API hiccup — degrade gracefully to the offline counter.
                pass
        return count_tokens_offline(text)

    def optimize(
        self,
        text: str,
        *,
        summarize: bool = False,
        max_chars: int = 24000,
        summary_ratio: float = 0.35,
    ) -> TextOptimizationResult:
        """Run the optimization strategies over ``text``.

        Deterministic reductions (unicode fold, framing/boilerplate strip, field
        collapsing, punctuation and filler collapse, paragraph dedup) always run
        offline. With ``summarize=True`` the summary tier is chosen by what's
        available, best first: Claude Haiku (API key) → a local Ollama model
        (``TOKENOPT_LOCAL_MODEL``, abstractive, no cloud tokens) → the deterministic
        entity-anchored extractive summarizer.
        """
        import time

        started = time.perf_counter()
        stages: list[str] = []
        summary_tier = "none"
        raw_tokens, _ = self._count(text)

        # Strategy 1 — deterministic offline reductions (Task A).
        optimized, reduce_stages = reduce_text(text)
        stages.extend(reduce_stages)

        # Strategy 2 — whitespace/dedupe compression, run BEFORE summarization so
        # repeated lines (huge in logs/boilerplate) are collapsed and can't survive
        # into — or dominate — the summary. Without this, summarizing a
        # duplicate-heavy document produced a WORSE result than not summarizing.
        compressed_changed = False
        pre = compress_prose(optimized, max_chars=max_chars)
        compressed_changed = compressed_changed or pre != optimized
        optimized = pre

        # Strategy 3 — summarization (optional).
        if summarize:
            if self.client is not None:
                optimized = self.client.complete(
                    system=_SUMMARY_SYSTEM,
                    user=f"Summarize the following document for an AI agent:\n\n{optimized}",
                    model=self.config.summary_model,
                    max_tokens=2048,
                    effort="low",
                    adaptive_thinking=False,
                )
                stages.append("summarize")
                summary_tier = "haiku"
            else:
                before = list(stages)
                optimized = self._local_or_extractive(optimized, summary_ratio, stages)
                added = [s for s in stages if s not in before]
                if "local-model-summarize" in added:
                    summary_tier = "local-model"
                elif "extractive-summarize" in added:
                    summary_tier = "extractive"

        # Final compression pass — tidy whitespace and enforce the char cap on the
        # (possibly summarized) text.
        post = compress_prose(optimized, max_chars=max_chars)
        compressed_changed = compressed_changed or post != optimized
        optimized = post
        if compressed_changed:
            stages.append("compress")

        optimized_tokens, token_method = self._count(optimized)
        cost = self.client.estimate_cost() if self.client is not None else 0.0
        duration_ms = (time.perf_counter() - started) * 1000.0

        return TextOptimizationResult(
            raw_text=text,
            optimized_text=optimized,
            raw_tokens=raw_tokens,
            optimized_tokens=optimized_tokens,
            token_method=token_method,
            stages=stages,
            estimated_cost_usd=cost,
            summary_tier=summary_tier,
            duration_ms=duration_ms,
        )


def build_prompt_request(
    optimized_text: str,
    *,
    system: str = "",
    task: str = "",
) -> dict[str, object]:
    """Assemble the smallest reasonable Claude request from optimized text (Task D).

    Returns a dict shaped for the Messages API: a stable ``system`` prefix (kept
    separate so prompt caching stays hot) and a single user turn holding a terse
    task line plus the optimized data under one compact delimiter — no repeated
    instructions, no restating the payload, no pretty-print padding.
    """
    parts: list[str] = []
    if task.strip():
        parts.append(task.strip())
    # One compact delimiter; the model doesn't need prose framing around the data.
    parts.append("<data>\n" + optimized_text.strip() + "\n</data>")
    request: dict[str, object] = {
        "messages": [{"role": "user", "content": "\n".join(parts)}],
    }
    if system.strip():
        request["system"] = system.strip()
    return request


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
