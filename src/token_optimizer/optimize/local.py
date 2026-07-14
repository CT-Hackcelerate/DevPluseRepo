"""Offline text reduction — real token savings with no API key.

Where ``compress.compress_prose`` only tidies whitespace and drops verbatim
duplicate lines (a near no-op on clean prose), this module does the work that
actually shrinks a real document without ever calling the model:

  * ``normalize_unicode``   — fancy Unicode → ASCII (cheaper BPE tokens)
  * ``strip_boilerplate``   — page numbers, headers/footers, rules, TOC leaders
  * ``collapse_punctuation``— decorative/repeated punctuation and bullet glyphs
  * ``substitute_fillers``  — verbose phrases → short equivalents
  * ``dedupe_paragraphs``   — near-duplicate paragraph removal
  * ``reduce_text``         — run all of the above (Task A)
  * ``extractive_summary``  — TextRank-style sentence selection (Task B, no LLM)

Every function is deterministic and offline. ``reduce_text`` returns the reduced
text plus the list of stages that actually changed something, so the UI can show
the user *what* fired instead of an empty stage list.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

# ── Task A.1 — Unicode → ASCII ──────────────────────────────────────────────

# Characters that a Claude tokenizer often splits into extra tokens, mapped to a
# cheap ASCII equivalent. NBSP / zero-width chars are normalized to plain space.
_UNICODE_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",  # single quotes
    "“": '"', "”": '"', "„": '"', "‟": '"',  # double quotes
    "–": "-", "—": "-", "―": "-", "−": "-",  # dashes/minus
    "…": "...",                                             # ellipsis
    " ": " ", " ": " ", " ": " ", " ": " ",  # fancy spaces
    "﻿": "", "​": "", "‌": "", "‍": "",      # zero-width
    "•": "-", "▪": "-", "●": "-", "⁃": "-",  # bullet glyphs
    "·": "-", "∙": "-", "‣": "-", "◦": "-",  # more bullets
    "™": "(TM)", "®": "(R)", "©": "(C)",          # symbols
    "ﬁ": "fi", "ﬂ": "fl",                             # ligatures
}
_UNICODE_RE = re.compile("|".join(map(re.escape, _UNICODE_MAP)))

# Emoji / pictographic ranges — decorative, pure token cost for an agent.
_EMOJI_RE = re.compile(
    "[" "\U0001f300-\U0001faff" "\U00002600-\U000027bf" "\U0001f1e6-\U0001f1ff" "]",
    flags=re.UNICODE,
)


def normalize_unicode(text: str) -> str:
    """Fold fancy Unicode to ASCII and drop decorative glyphs."""
    text = unicodedata.normalize("NFKC", text)
    text = _UNICODE_RE.sub(lambda m: _UNICODE_MAP[m.group(0)], text)
    text = _EMOJI_RE.sub("", text)
    return text


# ── Task A.2 — boilerplate stripping ────────────────────────────────────────

_BOILERPLATE_LINE = [
    re.compile(r"^\s*page\s+\d+\s*(of\s+\d+)?\s*$", re.IGNORECASE),
    re.compile(r"^\s*-?\s*\d+\s*-?\s*$"),                      # bare page number
    re.compile(r"^\s*(confidential|proprietary|internal use only)\b.*$", re.IGNORECASE),
    re.compile(r"^\s*(all rights reserved|copyright|\(c\)\s*\d{4})\b.*$", re.IGNORECASE),
    re.compile(r"^\s*[=_*~#-]{4,}\s*$"),                       # horizontal rules
    re.compile(r"^.*\.{4,}\s*\d+\s*$"),                        # TOC dot leaders
]


def strip_boilerplate(text: str) -> str:
    """Drop page numbers, running headers/footers, rules and TOC dot leaders."""
    out = [ln for ln in text.split("\n") if not any(p.match(ln) for p in _BOILERPLATE_LINE)]
    return "\n".join(out)


# ── Task A.3 — decorative / repeated punctuation ────────────────────────────

_PUNCT_RULES = [
    (re.compile(r"!{2,}"), "!"),
    (re.compile(r"\?{2,}"), "?"),
    (re.compile(r"\.{4,}"), "..."),
    (re.compile(r"-{2,}"), "-"),
    (re.compile(r"\*{2,}"), "*"),
    (re.compile(r"_{2,}"), "_"),
    (re.compile(r"~{2,}"), "~"),
    (re.compile(r"(,\s*){2,}"), ", "),
]


def collapse_punctuation(text: str) -> str:
    """Collapse runs of decorative/repeated punctuation to a single mark."""
    for pat, repl in _PUNCT_RULES:
        text = pat.sub(repl, text)
    return text


# ── Task A.4 — filler-phrase substitution ───────────────────────────────────

# Verbose phrase → concise equivalent. Ordered longest-first so nested phrases
# (e.g. "due to the fact that") win over their substrings.
_FILLER_MAP = {
    "due to the fact that": "because",
    "in the event that": "if",
    "in order to": "to",
    "for the purpose of": "to",
    "with regard to": "about",
    "with respect to": "about",
    "in relation to": "about",
    "at this point in time": "now",
    "at the present time": "now",
    "in the near future": "soon",
    "a large number of": "many",
    "a majority of": "most",
    "in spite of the fact that": "although",
    "in the process of": "",
    "it should be noted that": "",
    "please note that": "",
    "it is important to note that": "",
    "as a matter of fact": "",
    "needless to say": "",
}
# One alternation, longest phrase first, word-bounded, case-insensitive.
_FILLER_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(_FILLER_MAP, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def substitute_fillers(text: str) -> str:
    """Replace verbose filler phrases with short equivalents (or nothing)."""

    def _repl(m: re.Match) -> str:
        return _FILLER_MAP[m.group(0).lower()]

    text = _FILLER_RE.sub(_repl, text)
    # A dropped phrase can leave a double space or a space before punctuation.
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


# ── Task A.5 — near-duplicate paragraph dedup ───────────────────────────────

_NORM_RE = re.compile(r"\W+")


def _para_key(paragraph: str) -> str:
    """A normalized fingerprint: lowercased, punctuation/whitespace-insensitive."""
    return _NORM_RE.sub(" ", paragraph).strip().lower()


def dedupe_paragraphs(text: str) -> str:
    """Drop paragraphs whose normalized form has already been seen."""
    paragraphs = re.split(r"\n\s*\n", text)
    seen: set[str] = set()
    out: list[str] = []
    for para in paragraphs:
        key = _para_key(para)
        if not key:  # keep structural blank separators as-is
            out.append(para)
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(para)
    return "\n\n".join(out)


# ── Task A.6 — conversational / LLM framing removal ─────────────────────────

# Lines/sentences that are pure conversational packaging — common in
# LLM-generated or human-authored text, zero signal for a downstream agent.
_FRAMING_PATTERNS = [
    re.compile(r"^\s*(sure|certainly|absolutely|of course|great|no problem)[!,. ].*", re.IGNORECASE),
    re.compile(r"^\s*here('?s| is| are)\b.*", re.IGNORECASE),
    re.compile(r"^\s*(i|i'?ll|i can|i would|let me)\b.*\b(help|create|prepare|make|provide|show|explain)\b.*", re.IGNORECASE),
    re.compile(r"^\s*(if you('?d| would)? like|would you like|let me know|feel free|hope this helps|i hope|please let me know)\b.*", re.IGNORECASE),
    re.compile(r"^\s*(as an ai|i'?m an ai|as a language model)\b.*", re.IGNORECASE),
    re.compile(r"^\s*(in (summary|conclusion|short)|to summari[sz]e|overall)[,: ].*", re.IGNORECASE),
]
# Trailing follow-up questions ("Would you like ...?") — drop whole sentence.
_FRAMING_SENTENCE = re.compile(
    r"(?:^|\s)((?:would you like|shall i|do you want|should i|can i help)[^.?!]*\?)",
    re.IGNORECASE,
)


def strip_conversational_framing(text: str) -> str:
    """Remove conversational preamble, sign-offs, and follow-up offers."""
    kept = [ln for ln in text.split("\n") if not any(p.match(ln) for p in _FRAMING_PATTERNS)]
    out = "\n".join(kept)
    return _FRAMING_SENTENCE.sub("", out).strip()


# ── Task A.7 — structure-aware field extraction ─────────────────────────────

# A "label-only" line: a short title followed by a colon and nothing else, e.g.
# "Summary:", "Steps to Reproduce:". The value lives on the following line(s).
_LABEL_ONLY = re.compile(r"^\s*([A-Z][A-Za-z0-9 /()&-]{0,38}):\s*$")
# A placeholder value with no real content — drop the whole field.
_PLACEHOLDER = re.compile(r"^\s*[\[(].*(leave blank|tbd|n/?a|optional|fill in|assign).*[\])]\s*$", re.IGNORECASE)


def collapse_field_blocks(text: str) -> str:
    """Collapse ``Label:`` / value-on-next-lines blocks into tight ``label: value``.

    Structured issue text (Jira tickets, bug reports) spends most of its tokens on
    blank lines and label/value line breaks. Folding each block onto one line —
    ``Summary:\\ntext`` → ``Summary: text`` — and joining multi-line values with
    "; " removes that structural overhead while keeping every field intact.
    Fields whose only value is a placeholder are dropped entirely.
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    changed = False
    while i < len(lines):
        m = _LABEL_ONLY.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        label = m.group(1).strip()
        # Gather value lines until the next label-only line (or end).
        i += 1
        values: list[str] = []
        while i < len(lines) and not _LABEL_ONLY.match(lines[i]):
            val = lines[i].strip()
            if val and not _PLACEHOLDER.match(val):
                values.append(val)
            i += 1
        changed = True
        if values:
            out.append(f"{label}: {'; '.join(values)}")
        # else: field had no real value — drop it entirely.
    result = "\n".join(out)
    return result if changed else text


# ── Task A — full deterministic reduction ───────────────────────────────────


def reduce_text(text: str) -> tuple[str, list[str]]:
    """Run every deterministic reduction, returning (reduced, stages_applied).

    A stage name is recorded only if that stage actually changed the text, so the
    caller can report exactly what fired.
    """
    stages: list[str] = []
    steps = [
        ("unicode", normalize_unicode),
        ("framing", strip_conversational_framing),
        ("boilerplate", strip_boilerplate),
        ("fields", collapse_field_blocks),
        ("punctuation", collapse_punctuation),
        ("filler", substitute_fillers),
        ("dedupe-paragraphs", dedupe_paragraphs),
    ]
    for name, fn in steps:
        new = fn(text)
        if new != text:
            stages.append(name)
        text = new
    return text, stages


# ── Task B — offline extractive summarization (TextRank-style, no LLM) ───────

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
# Common English stopwords — excluded from the term-overlap scoring so sentences
# aren't ranked highly just for sharing "the" / "and".
_STOPWORDS = frozenset(
    """a an and are as at be but by for from has have he her his i in is it its of on or
    that the their them they this to was we were will with you your our us not no do does
    did can could would should may might must than then there here what which who whom""".split()
)
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences on terminal punctuation (best-effort)."""
    flat = re.sub(r"\s+", " ", text).strip()
    if not flat:
        return []
    return [s.strip() for s in _SENT_SPLIT.split(flat) if s.strip()]


def _content_terms(sentence: str) -> list[str]:
    return [w for w in _TOKEN_RE.findall(sentence.lower()) if w not in _STOPWORDS and len(w) > 1]


def _sentence_scores(sentences: list[str]) -> list[float]:
    """Centrality scoring: rank a sentence by how much it shares the doc's theme.

    Each content term is weighted by its *sentence frequency* — how many sentences
    contain it — so words that recur across the document (its theme) pull their
    sentences up, while one-off asides sink. This is the TextRank intuition (a
    sentence is important if it overlaps with many others) without the iterative
    eigenvector step. Scores are length-normalized so a sentence isn't ranked
    highly just for being long.
    """
    terms_per_sent = [_content_terms(s) for s in sentences]
    doc_freq: Counter = Counter()
    for terms in terms_per_sent:
        for term in set(terms):
            doc_freq[term] += 1

    scores: list[float] = []
    for terms in terms_per_sent:
        if not terms:
            scores.append(0.0)
            continue
        tf = Counter(terms)
        raw = sum(tf[t] * doc_freq[t] for t in tf)
        scores.append(raw / len(terms))  # length-normalize so long ≠ important
    return scores


# Must-keep entities: dropping a sentence that carries one of these usually loses
# a fact an agent needs (error codes, versions, IDs, labels, paths, numbers).
_MUST_KEEP = re.compile(
    r"""(
        \b\d{3,}\b                     # status/error codes, counts (500, 404, 1234)
        | \bv?\d+\.\d+(\.\d+)?\b        # versions (2.3.1, v1.0)
        | \b[A-Z]{2,}-\d+\b            # issue keys (ABC-123)
        | \b[A-Z][a-z]+[A-Z]\w*\b     # CamelCase identifiers (NullPointerException)
        | \b\w+\.(py|js|ts|java|go|rb|cs|cpp|json|yaml|yml|log|txt)\b  # file paths
        | https?://\S+                 # URLs
        | \b\w+@\w+\.\w+\b            # emails
        | \b[A-Za-z]:\\|/\w+/\w+       # windows/unix paths
    )""",
    re.VERBOSE,
)


def _has_must_keep(sentence: str) -> bool:
    return bool(_MUST_KEEP.search(sentence))


def extractive_summary(text: str, *, ratio: float = 0.35, min_sentences: int = 3) -> str:
    """Keep the top-ranked sentences (in original order) — no LLM required.

    ``ratio`` is the fraction of sentences to keep. Sentences carrying a must-keep
    entity (error codes, versions, IDs, file paths, URLs, labels) are *always*
    retained so summarization never silently drops a fact an agent needs; the
    remaining budget is filled by centrality score. Sentence order is preserved so
    the summary still reads coherently. Below ``min_sentences`` the text is
    returned unchanged — there's nothing to gain from summarizing a few lines.
    """
    sentences = split_sentences(text)
    if len(sentences) <= min_sentences:
        return text.strip()

    keep = max(min_sentences, math.ceil(len(sentences) * ratio))
    if keep >= len(sentences):
        return text.strip()

    # 1. Anchor: every sentence with a must-keep entity is retained outright.
    anchored = {i for i, s in enumerate(sentences) if _has_must_keep(s)}

    # 2. Fill the rest of the budget by centrality score.
    scores = _sentence_scores(sentences)
    remaining = [i for i in range(len(sentences)) if i not in anchored]
    remaining.sort(key=lambda i: scores[i], reverse=True)

    chosen = set(anchored)
    for i in remaining:
        if len(chosen) >= keep:
            break
        chosen.add(i)

    # If anchors alone already exceed the budget, keep them all — losing a fact is
    # worse than exceeding the target ratio.
    return " ".join(sentences[i] for i in sorted(chosen))
