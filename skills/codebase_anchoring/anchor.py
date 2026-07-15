"""Anchor plan steps to real ``file:line`` references.

Given a ``CodebaseIndex`` and an AI-generated plan (free text or a list of
steps), resolve every symbol-like mention to a verifiable ``file:line`` anchor.
Mentions that can't be resolved are flagged rather than silently accepted — this
is what eliminates hallucinated references and the wasted regeneration loops that
follow them.

Two entry points:
  * ``anchor_text`` — scan free-form text, append anchors inline where a token
    matches an indexed symbol.
  * ``anchor_plan`` — take a list of step strings, return structured ``Anchor``
    results (resolved / unresolved) per step for programmatic use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .indexer import CodebaseIndex, CodeSymbol

# Identifier-ish tokens: CamelCase, snake_case, dotted paths, or file names.
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
# Explicit path mentions like src/foo/bar.py already carry their location.
_PATH = re.compile(r"[\w./-]+\.[A-Za-z]{1,4}(?::\d+)?")


@dataclass
class Anchor:
    """The anchoring outcome for one plan step."""

    step: str
    resolved: list[CodeSymbol] = field(default_factory=list)
    unresolved_terms: list[str] = field(default_factory=list)

    @property
    def is_anchored(self) -> bool:
        return bool(self.resolved)

    def render(self) -> str:
        if self.resolved:
            refs = ", ".join(s.anchor for s in self.resolved)
            return f"{self.step}  [anchored: {refs}]"
        if self.unresolved_terms:
            return f"{self.step}  [unresolved: {', '.join(self.unresolved_terms)}]"
        return self.step


def _candidate_terms(text: str) -> list[str]:
    """Extract identifier-like candidate terms from a step, longest first."""
    terms = set(_IDENT.findall(text))
    # Prefer longer, more distinctive names first.
    return sorted(terms, key=len, reverse=True)


def anchor_plan(
    plan_steps: list[str],
    index: CodebaseIndex,
    *,
    max_refs_per_step: int = 3,
) -> list[Anchor]:
    """Resolve each step's symbol mentions to real ``file:line`` anchors.

    A step is considered anchored if at least one of its identifier-like terms
    matches an indexed symbol. Terms that look like real symbols (CamelCase or
    snake_case) but resolve to nothing are recorded as ``unresolved_terms`` so a
    caller can flag potential hallucinations.
    """
    results: list[Anchor] = []
    for step in plan_steps:
        resolved: list[CodeSymbol] = []
        seen_anchor: set[str] = set()
        unresolved: list[str] = []

        for term in _candidate_terms(step):
            if len(resolved) >= max_refs_per_step:
                break
            matches = index.lookup(term)
            if not matches:
                matches = index.search(term, limit=1)
            if matches:
                for sym in matches[: max_refs_per_step - len(resolved)]:
                    if sym.anchor not in seen_anchor:
                        seen_anchor.add(sym.anchor)
                        resolved.append(sym)
            elif _looks_like_symbol(term):
                unresolved.append(term)

        results.append(Anchor(step=step, resolved=resolved, unresolved_terms=unresolved))
    return results


def _looks_like_symbol(term: str) -> bool:
    """Heuristic: does ``term`` look like a code symbol worth flagging?"""
    has_camel = bool(re.search(r"[a-z][A-Z]", term))
    has_snake = "_" in term
    return has_camel or has_snake


def anchor_text(text: str, index: CodebaseIndex) -> str:
    """Annotate free-form text: append ``(file:line)`` after resolvable symbols.

    Splits the text into lines and treats each non-empty line as a step so the
    output stays readable while gaining verifiable anchors.
    """
    lines = text.split("\n")
    steps = [ln for ln in lines if ln.strip()]
    anchors = {a.step: a for a in anchor_plan(steps, index)}

    out: list[str] = []
    for line in lines:
        anc = anchors.get(line)
        if anc and anc.resolved:
            refs = ", ".join(s.anchor for s in anc.resolved)
            out.append(f"{line}  ({refs})")
        else:
            out.append(line)
    return "\n".join(out)


def anchoring_accuracy(anchors: list[Anchor]) -> float:
    """Fraction of steps that resolved to at least one real anchor (0.0-1.0)."""
    if not anchors:
        return 0.0
    anchored = sum(1 for a in anchors if a.is_anchored)
    return anchored / len(anchors)
