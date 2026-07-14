"""Strategy 3 — Smart summarization.

When an input is still large after pre-filtering and compression, pre-summarize it
with a cheap, fast model (Haiku) so the expensive model (Opus) reasons over a short
summary instead of the raw bulk. Below the threshold, we skip the extra call and
pass the text through unchanged — the summary call is only worth it when the input
is genuinely large.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..llm.client import ClaudeClient

_SUMMARY_SYSTEM = (
    "You compress technical content for a downstream AI agent, not a human. "
    "Preserve every fact that could affect a decision: identifiers, error messages, "
    "root causes, file paths, numbers, and explicit requests. Drop pleasantries, "
    "duplication, and formatting. Output dense prose or bullet points, no preamble."
)


def summarize_if_large(
    client: "ClaudeClient",
    text: str,
    *,
    threshold_tokens: int = 2000,
    summary_model: str = "claude-haiku-4-5",
    max_summary_tokens: int = 1024,
    label: str = "content",
) -> str:
    """Return ``text`` unchanged if small, else a Haiku-generated summary.

    Token counting uses the API's ``count_tokens`` endpoint, so the threshold is
    measured against the model that will actually read it.
    """
    tokens = client.count_tokens(
        messages=[{"role": "user", "content": text}], model=summary_model
    )
    if tokens <= threshold_tokens:
        return text

    return client.complete(
        system=_SUMMARY_SYSTEM,
        user=f"Summarize the following {label} for an AI agent:\n\n{text}",
        model=summary_model,
        max_tokens=max_summary_tokens,
        effort="low",
        adaptive_thinking=False,
        cache_system=True,
        use_local_cache=True,
    )
