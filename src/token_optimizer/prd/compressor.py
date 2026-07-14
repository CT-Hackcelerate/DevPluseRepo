"""PRD compression — verbose prose to dense requirement atoms.

A raw PRD is mostly framing: executive summaries, background, restated goals,
polite hedging, and formatting noise. Only a fraction carries a *decision* — a
goal, a constraint, an acceptance criterion. This module extracts those
decision-relevant atoms and re-renders them in a compact, structured form.

The pipeline is fully deterministic and offline (no LLM):

  1. Normalize + strip boilerplate (reuse ``optimize.local`` / ``compress``).
  2. Segment into sections/lines.
  3. Classify each unit into a requirement *category* (goal, constraint,
     acceptance-criterion, non-functional, out-of-scope, dependency, other).
  4. Drop low-signal "other" prose and de-duplicate near-identical atoms.
  5. Preserve acceptance criteria *verbatim* — never paraphrase what the build
     will be checked against.
  6. Re-render as terse bullet atoms grouped by category.

Result: a structured PRD that typically costs ~1/3 the tokens of the original.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..optimize.local import (
    collapse_punctuation,
    normalize_unicode,
    strip_boilerplate,
    substitute_fillers,
)
from ..optimize.tokens import count_tokens_offline

# ── requirement categories & their trigger cues ─────────────────────────────

# Ordered by priority: the first category whose cue matches wins. Acceptance
# criteria are checked first because they are the most decision-critical and
# must be preserved verbatim.
_CATEGORY_CUES: list[tuple[str, re.Pattern]] = [
    (
        "acceptance-criteria",
        re.compile(
            r"\b(acceptance criteri|given\b.*\bwhen\b|then\b.*\bshould|"
            r"definition of done|verif|test that|pass(es|ed)? when)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "constraint",
        re.compile(
            r"\b(must not|shall not|cannot|constraint|limit(ed)?|no more than|"
            r"at most|at least|within \d|budget|deadline|by (end of|EOD|Q[1-4]))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "non-functional",
        re.compile(
            r"\b(performance|latency|throughput|scal(e|ability)|availabilit|"
            r"security|compliance|accessib|reliab|uptime|SLA|GDPR|encrypt)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "out-of-scope",
        re.compile(r"\b(out of scope|not in scope|will not|won'?t|non-goal|excluded)\b", re.IGNORECASE),
    ),
    (
        "dependency",
        re.compile(r"\b(depends on|dependency|requires|blocked by|prerequisite|integrat)\b", re.IGNORECASE),
    ),
    (
        "goal",
        re.compile(
            r"\b(must|shall|should|will|need(s)? to|the system|user(s)? can|"
            r"as a .* i want|support|enable|allow|provide|implement|add|"
            r"objective|goal)\b",
            re.IGNORECASE,
        ),
    ),
]

# Lines that are pure framing — never carry a requirement decision.
_FRAMING_LINE = re.compile(
    r"^\s*(executive summary|background|overview|introduction|context|"
    r"table of contents|revision history|document (owner|status)|"
    r"stakeholders?|appendix|references?)\s*:?\s*$",
    re.IGNORECASE,
)

# Hedging / filler openers that add tokens but no decision content.
_HEDGE = re.compile(
    r"^\s*(basically|essentially|in general|generally speaking|as mentioned|"
    r"as noted|of course|obviously|it is worth noting that|"
    r"for reference|please note that|note that|kindly)\b[,: ]*",
    re.IGNORECASE,
)

_HEADING = re.compile(r"^\s*(#{1,6}\s+|\d+(\.\d+)*\s+|[A-Z][A-Za-z ]{0,40}:)\s*")
_BULLET = re.compile(r"^\s*([-*•‣◦·]|\d+[.)])\s+")


@dataclass
class RequirementAtom:
    """A single decision-relevant unit extracted from the PRD."""

    category: str
    text: str

    def render(self) -> str:
        return f"- {self.text}"


@dataclass
class PRDCompressionResult:
    raw_text: str
    compressed_text: str
    atoms: list[RequirementAtom]
    raw_tokens: int
    compressed_tokens: int
    token_method: str
    dropped_units: int = 0

    @property
    def tokens_saved(self) -> int:
        return max(0, self.raw_tokens - self.compressed_tokens)

    @property
    def reduction_pct(self) -> float:
        if self.raw_tokens == 0:
            return 0.0
        return 100.0 * self.tokens_saved / self.raw_tokens

    def summary(self) -> str:
        return (
            f"PRD: raw={self.raw_tokens} tok  ->  compressed={self.compressed_tokens} tok  "
            f"(saved {self.tokens_saved} tok, {self.reduction_pct:.1f}% smaller)  "
            f"| {len(self.atoms)} requirement atoms kept, {self.dropped_units} units dropped"
        )


def _split_units(text: str) -> list[str]:
    """Break the PRD into candidate units: bullets and sentences.

    Bullet/numbered lines are kept whole, with wrapped continuation lines joined
    back on (so a multi-line acceptance criterion stays one unit). Free prose
    paragraphs are split into sentences so a single decision buried in a
    paragraph can still be extracted.
    """
    units: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        current_bullet: str | None = None
        for line in block.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if _BULLET.match(line):
                if current_bullet is not None:
                    units.append(current_bullet)
                current_bullet = _BULLET.sub("", stripped)
                continue
            if _HEADING.match(line):
                if current_bullet is not None:
                    units.append(current_bullet)
                    current_bullet = None
                units.append(stripped)
                continue
            # Non-bullet line.
            if current_bullet is not None:
                # Wrapped continuation of the current bullet — join it on.
                current_bullet = f"{current_bullet} {stripped}"
                continue
            # Free prose line — split into sentences.
            for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", stripped):
                sent = sent.strip()
                if sent:
                    units.append(sent)
        if current_bullet is not None:
            units.append(current_bullet)
    return units


def _classify(unit: str) -> str | None:
    """Return the requirement category of ``unit`` or ``None`` to drop it."""
    for category, pattern in _CATEGORY_CUES:
        if pattern.search(unit):
            return category
    return None


def _tidy(unit: str) -> str:
    """Trim hedging/filler and normalize a unit's punctuation."""
    unit = _HEDGE.sub("", unit)
    unit = substitute_fillers(unit)
    unit = collapse_punctuation(unit)
    return unit.strip(" \t-*•·")


# Emit order for categories in the rendered output.
_CATEGORY_ORDER = [
    "goal",
    "acceptance-criteria",
    "constraint",
    "non-functional",
    "dependency",
    "out-of-scope",
]

_CATEGORY_TITLES = {
    "goal": "GOALS",
    "acceptance-criteria": "ACCEPTANCE CRITERIA",
    "constraint": "CONSTRAINTS",
    "non-functional": "NON-FUNCTIONAL",
    "dependency": "DEPENDENCIES",
    "out-of-scope": "OUT OF SCOPE",
}


def render_atoms(atoms: list[RequirementAtom]) -> str:
    """Render atoms as a compact, category-grouped structured PRD."""
    by_cat: dict[str, list[RequirementAtom]] = {}
    for atom in atoms:
        by_cat.setdefault(atom.category, []).append(atom)

    blocks: list[str] = []
    for cat in _CATEGORY_ORDER:
        items = by_cat.get(cat)
        if not items:
            continue
        title = _CATEGORY_TITLES[cat]
        lines = "\n".join(a.render() for a in items)
        blocks.append(f"## {title}\n{lines}")
    return "\n\n".join(blocks)


def compress_prd(text: str) -> PRDCompressionResult:
    """Compress a raw PRD into structured requirement atoms.

    Acceptance criteria are preserved verbatim (only whitespace-normalized) so
    the build is never checked against a paraphrase. Every other atom is tidied
    of hedging/filler. Near-duplicate atoms (same normalized fingerprint) are
    dropped once.
    """
    raw_tokens, _ = count_tokens_offline(text)

    # Pre-clean: fold unicode, strip page/footer boilerplate.
    cleaned = strip_boilerplate(normalize_unicode(text))

    units = _split_units(cleaned)
    atoms: list[RequirementAtom] = []
    seen: set[str] = set()
    dropped = 0

    for unit in units:
        if _FRAMING_LINE.match(unit):
            dropped += 1
            continue
        category = _classify(unit)
        if category is None:
            dropped += 1
            continue

        if category == "acceptance-criteria":
            # Preserve verbatim — only collapse internal whitespace.
            atom_text = re.sub(r"\s+", " ", unit).strip()
        else:
            atom_text = _tidy(unit)
        if not atom_text:
            dropped += 1
            continue

        fingerprint = re.sub(r"\W+", " ", atom_text).strip().lower()
        if fingerprint in seen:
            dropped += 1
            continue
        seen.add(fingerprint)
        atoms.append(RequirementAtom(category=category, text=atom_text))

    compressed_text = render_atoms(atoms)
    compressed_tokens, method = count_tokens_offline(compressed_text)

    return PRDCompressionResult(
        raw_text=text,
        compressed_text=compressed_text,
        atoms=atoms,
        raw_tokens=raw_tokens,
        compressed_tokens=compressed_tokens,
        token_method=method,
        dropped_units=dropped,
    )
