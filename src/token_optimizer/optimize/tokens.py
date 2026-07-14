"""Local token estimation — a fallback when the API is not available.

The accurate way to count Claude tokens is the ``count_tokens`` endpoint (see
``ClaudeClient.count_tokens``), which needs an API key and a network call. For
offline use — e.g. compressing a document with no key configured — this module
gives a fast, reasonable estimate so the UI can still show a savings figure.

The heuristic blends a character-based and word-based estimate; for English prose
it lands within ~10-15% of the real BPE count, which is good enough to compare a
"before" and "after" of the *same* text.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"\w+|[^\w\s]")


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in ``text`` without calling the API."""
    if not text:
        return 0
    char_est = len(text) / 4.0
    token_like = len(_WORD.findall(text))
    word_est = token_like * 0.75
    return max(1, round((char_est + word_est) / 2))
