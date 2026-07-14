"""Optional local-model summarization — abstractive quality, zero cloud tokens.

The offline deterministic + extractive strategies never *rewrite* text; to match
the density of the Claude-Haiku pass without spending cloud tokens, run a model
locally. This backend talks to a locally-running `Ollama <https://ollama.com>`
server over HTTP (using the ``httpx`` we already depend on — no new package), so
if you have Ollama installed and a model pulled (e.g. ``ollama pull llama3.2``),
summarization becomes truly abstractive while staying entirely on your machine.

It is strictly optional and degrades gracefully: if Ollama isn't running, the
model isn't pulled, or the call fails, ``summarize`` returns ``None`` and the
pipeline falls back to the deterministic extractive summarizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

# Same intent as the Claude summary system prompt — dense, agent-facing output.
_LOCAL_SUMMARY_INSTRUCTION = (
    "You compress technical content for a downstream AI agent, not a human. "
    "Preserve every fact that could affect a decision: identifiers, error messages, "
    "root causes, file paths, version numbers, and explicit requests. Drop "
    "pleasantries, duplication, and formatting. Output dense prose or tight bullet "
    "points, no preamble, no follow-up questions.\n\n"
    "Compress the following for an AI agent:\n\n"
)


@dataclass
class LocalModelSummarizer:
    """Summarize via a local Ollama server. Never raises to the caller."""

    model: str
    base_url: str = "http://localhost:11434"
    timeout: float = 120.0

    def available(self) -> bool:
        """True if the Ollama server is reachable and has ``model`` pulled."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
            resp.raise_for_status()
            tags = resp.json().get("models", [])
            names = {m.get("name", "").split(":")[0] for m in tags}
            return self.model.split(":")[0] in names
        except Exception:
            return False

    def summarize(self, text: str) -> Optional[str]:
        """Return an abstractive summary, or ``None`` if the local model can't run."""
        try:
            resp = httpx.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": _LOCAL_SUMMARY_INSTRUCTION + text,
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            out = (resp.json().get("response") or "").strip()
            return out or None
        except Exception:
            # Server down, model missing, timeout — caller falls back to extractive.
            return None


def get_local_summarizer(model: str, base_url: str = "http://localhost:11434") -> Optional[LocalModelSummarizer]:
    """Return a ready summarizer if a local model is configured and reachable, else None."""
    if not model:
        return None
    summarizer = LocalModelSummarizer(model=model, base_url=base_url)
    return summarizer if summarizer.available() else None
