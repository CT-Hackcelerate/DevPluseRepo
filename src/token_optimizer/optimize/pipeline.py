"""The optimization pipeline: composes all four strategies and reports savings.

Given raw payloads pulled from JIRA/DevOps tools, ``OptimizedRunner`` runs them
through pre-filter → compress → summarize before handing the result to Claude with
prompt caching enabled, and reports exactly how many tokens were saved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from ..config import Config
from ..llm.cache import ResponseCache
from ..llm.client import ClaudeClient
from .compress import compress_text
from .prefilter import prefilter_fields
from .summarize import summarize_if_large


@dataclass
class OptimizationResult:
    answer: str
    raw_tokens: int
    optimized_tokens: int
    usage: dict[str, int]
    estimated_cost_usd: float

    @property
    def tokens_saved(self) -> int:
        return max(0, self.raw_tokens - self.optimized_tokens)

    @property
    def reduction_pct(self) -> float:
        if self.raw_tokens == 0:
            return 0.0
        return 100.0 * self.tokens_saved / self.raw_tokens

    def summary(self) -> str:
        return (
            f"raw={self.raw_tokens} tok  ->  optimized={self.optimized_tokens} tok  "
            f"({self.reduction_pct:.1f}% smaller prompt)  "
            f"| local cache hits: {self.usage.get('local_cache_hits', 0)}  "
            f"| cache reads: {self.usage.get('cache_read_input_tokens', 0)} tok  "
            f"| est. cost ${self.estimated_cost_usd:.4f}"
        )


@dataclass
class OptimizedRunner:
    """Runs a task over one or more raw items with all optimizations applied."""

    config: Config
    client: ClaudeClient = field(init=False)

    def __post_init__(self) -> None:
        self.config.require("anthropic_api_key")
        cache = ResponseCache(self.config.cache_dir)
        self.client = ClaudeClient(
            api_key=self.config.anthropic_api_key,
            model=self.config.model,
            cache=cache,
        )

    def _optimize_item(
        self,
        item: dict[str, Any],
        *,
        profile: str,
        summarize: bool,
    ) -> str:
        # 1. Local pre-filter: keep only task-relevant fields.
        filtered = prefilter_fields(item, profile)
        rendered = json.dumps(filtered, indent=None, ensure_ascii=False, default=str)
        # 2. Compress: strip noise, dedupe, truncate.
        rendered = compress_text(rendered, max_chars=12000)
        # 3. Smart summarize (only if still large).
        if summarize:
            rendered = summarize_if_large(
                self.client,
                rendered,
                summary_model=self.config.summary_model,
                label=profile,
            )
        return rendered

    def run(
        self,
        *,
        system: str,
        task: str,
        items: list[dict[str, Any]],
        profile: str,
        summarize: bool = True,
        max_tokens: int = 4096,
        effort: str = "high",
    ) -> OptimizationResult:
        """Optimize ``items`` and run one Claude call answering ``task`` over them.

        ``system`` is the stable, cached instruction prefix. Per-run ``task`` and
        the (optimized) item data go in the user turn so the cache prefix stays hot.
        """
        # Baseline: what the raw, unoptimized prompt would have cost.
        raw_blob = json.dumps(items, ensure_ascii=False, default=str)
        raw_tokens = self.client.count_tokens(
            messages=[{"role": "user", "content": f"{task}\n\n{raw_blob}"}],
            system=system,
        )

        optimized_parts = [
            self._optimize_item(it, profile=profile, summarize=summarize) for it in items
        ]
        optimized_blob = "\n\n---\n\n".join(optimized_parts)
        user = f"{task}\n\nDATA:\n{optimized_blob}"

        optimized_tokens = self.client.count_tokens(
            messages=[{"role": "user", "content": user}], system=system
        )

        answer = self.client.complete(
            system=system,
            user=user,
            max_tokens=max_tokens,
            effort=effort,
        )

        return OptimizationResult(
            answer=answer,
            raw_tokens=raw_tokens,
            optimized_tokens=optimized_tokens,
            usage=self.client.usage.as_dict(),
            estimated_cost_usd=self.client.estimate_cost(),
        )
