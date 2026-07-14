"""Local token counting — a fallback when the API is not available.

The accurate way to count Claude tokens is the ``count_tokens`` endpoint (see
``ClaudeClient.count_tokens``), which needs an API key and a network call. For
offline use — e.g. compressing a document with no key configured — this module
counts tokens without the network.

Two offline backends, best first:

  1. ``tiktoken`` (``cl100k_base``) — a real BPE tokenizer. Not Claude's exact
     vocabulary, but a far better proxy than a character heuristic and, crucially,
     it counts the *same way* for before/after so the reduction figure is honest.
  2. A blended char/word heuristic — used only when ``tiktoken`` isn't installed.
     Lands within ~10-15% of the real count for English prose.

Use ``count_tokens_offline`` for a count plus which backend produced it.
"""

from __future__ import annotations

import re
from functools import lru_cache

_WORD = re.compile(r"\w+|[^\w\s]")


@lru_cache(maxsize=1)
def _tiktoken_encoding():
    """Return a cached tiktoken encoding, or ``None`` if tiktoken isn't available."""
    try:
        import tiktoken
    except ImportError:
        return None
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        # e.g. no cached vocab file and no network to fetch it.
        return None


def _heuristic_tokens(text: str) -> int:
    """Blended char/word estimate — the last-resort backend."""
    char_est = len(text) / 4.0
    token_like = len(_WORD.findall(text))
    word_est = token_like * 0.75
    return max(1, round((char_est + word_est) / 2))


def count_tokens_offline(text: str) -> tuple[int, str]:
    """Count tokens offline, returning (count, method).

    ``method`` is ``"tiktoken"`` when the real BPE tokenizer was used, else
    ``"estimate"`` for the heuristic fallback.
    """
    if not text:
        return 0, "tiktoken" if _tiktoken_encoding() is not None else "estimate"
    enc = _tiktoken_encoding()
    if enc is not None:
        return len(enc.encode(text, disallowed_special=())), "tiktoken"
    return _heuristic_tokens(text), "estimate"


def estimate_tokens(text: str) -> int:
    """Estimate tokens in ``text`` without calling the API (best offline backend)."""
    if not text:
        return 0
    return count_tokens_offline(text)[0]
