"""Strategy 2 — Context compression.

Deterministic, lossless-ish text reduction: strip boilerplate, collapse
whitespace, drop duplicate lines (huge win on CI logs and stack traces), and
head/tail-truncate anything still too long. No LLM involved.
"""

from __future__ import annotations

import re

# Lines that carry no signal for an LLM reasoning about a build/log.
_NOISE_PATTERNS = [
    re.compile(r"^\s*$"),  # blank
    re.compile(r"^\s*(INFO|DEBUG|TRACE)\b", re.IGNORECASE),
    re.compile(r"^\s*at\s+[\w.$]+\([\w.]+:\d+\)\s*$"),  # deep stack frames
    re.compile(r"^\s*\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"),  # bare timestamps
    re.compile(r"^\s*(Downloading|Downloaded|Resolving|Fetching)\b", re.IGNORECASE),
]

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def strip_noise(text: str, keep_errors: bool = True) -> str:
    """Drop low-signal lines. Error/warning lines are always kept."""
    out: list[str] = []
    for line in text.splitlines():
        clean = _ANSI.sub("", line)
        if keep_errors and re.search(r"\b(error|fail|exception|fatal|warn)", clean, re.IGNORECASE):
            out.append(clean.rstrip())
            continue
        if any(p.search(clean) for p in _NOISE_PATTERNS):
            continue
        out.append(clean.rstrip())
    return "\n".join(out)


def dedupe_lines(text: str) -> str:
    """Remove consecutive and repeated identical lines, noting the count."""
    seen: dict[str, int] = {}
    order: list[str] = []
    for line in text.splitlines():
        if line not in seen:
            seen[line] = 0
            order.append(line)
        seen[line] += 1
    out = []
    for line in order:
        if seen[line] > 1:
            out.append(f"{line}    (x{seen[line]})")
        else:
            out.append(line)
    return "\n".join(out)


def head_tail_truncate(text: str, max_chars: int) -> str:
    """Keep the head and tail of an over-long string; the middle rarely matters."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    omitted = len(text) - 2 * half
    return f"{text[:half]}\n\n... [{omitted} chars omitted] ...\n\n{text[-half:]}"


def compress_text(
    text: str,
    max_chars: int = 12000,
    keep_errors: bool = True,
) -> str:
    """Full compression pass: strip noise → dedupe → truncate."""
    text = strip_noise(text, keep_errors=keep_errors)
    text = dedupe_lines(text)
    text = head_tail_truncate(text, max_chars)
    return text


_WS_RUN = re.compile(r"[ \t]{2,}")
_BLANK_RUN = re.compile(r"\n\s*\n\s*\n+")


def compress_prose(text: str, max_chars: int = 24000) -> str:
    """Compress a prose document (e.g. a Word file's text).

    Prose has no log-noise lines to strip, so the win comes from collapsing
    redundant whitespace, deduping repeated lines, and truncating an over-long
    tail. Runs of blank lines are squeezed to a single separator and multiple
    spaces/tabs to one — Claude pays for every whitespace token.
    """
    # Normalise line endings and trim trailing spaces on each line.
    lines = [_WS_RUN.sub(" ", ln.rstrip()) for ln in text.replace("\r\n", "\n").split("\n")]
    text = "\n".join(lines)
    # Squeeze 3+ consecutive blank lines down to one blank line.
    text = _BLANK_RUN.sub("\n\n", text)
    # Drop lines repeated verbatim (boilerplate headers/footers, copy-paste).
    text = dedupe_lines(text)
    return head_tail_truncate(text.strip(), max_chars)


def compress_diff(diff: str, max_chars: int = 16000, context: int = 2) -> str:
    """Compress a unified git diff for review.

    Keeps file headers, hunk headers, and changed (+/-) lines. Unchanged context
    lines are the bulk of a diff and carry little review signal, so we keep only
    ``context`` of them around each change and collapse the rest into a marker.
    """
    lines = diff.splitlines()
    out: list[str] = []
    pending_context: list[str] = []

    def flush_context(keep_trailing: bool) -> None:
        nonlocal pending_context
        if not pending_context:
            return
        if len(pending_context) <= context * 2:
            out.extend(pending_context)
        else:
            out.extend(pending_context[:context])
            out.append(f"    ... {len(pending_context) - context * 2} unchanged lines ...")
            if keep_trailing:
                out.extend(pending_context[-context:])
        pending_context = []

    for line in lines:
        is_meta = line.startswith(("diff --git", "index ", "--- ", "+++ ", "@@", "new file", "deleted file", "rename "))
        is_change = line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        if is_meta or is_change:
            flush_context(keep_trailing=True)
            out.append(line)
        else:
            pending_context.append(line)
    flush_context(keep_trailing=False)

    return head_tail_truncate("\n".join(out), max_chars)
