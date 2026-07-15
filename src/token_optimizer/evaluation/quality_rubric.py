"""25-point quality rubric — score an AI plan across five dimensions.

Five dimensions, 0-5 each, total 25:

  1. correctness      — does the plan address the stated requirements?
  2. completeness     — are all requirement atoms covered?
  3. anchoring        — are steps grounded in verifiable file:line references?
  4. actionability    — are steps concrete and executable (not vague)?
  5. no-hallucination — absence of unresolved/invented references.

Scoring is deterministic and evidence-based so A/B comparisons are reproducible
("blind" in the sense that the same inputs always yield the same score, with no
model-in-the-loop subjectivity). Each dimension has a small, transparent scorer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from codebase_anchoring.anchor import Anchor, anchoring_accuracy

_VAGUE = re.compile(
    r"\b(somehow|maybe|probably|etc\.?|and so on|as needed|appropriately|"
    r"handle (it|things)|do the needful|figure out)\b",
    re.IGNORECASE,
)
_ACTION_VERB = re.compile(
    r"\b(add|create|update|remove|delete|modify|refactor|implement|write|"
    r"rename|move|extract|inject|register|configure|validate|test|call|return|"
    r"replace|import|export|wire|connect)\b",
    re.IGNORECASE,
)


@dataclass
class QualityScore:
    correctness: int
    completeness: int
    anchoring: int
    actionability: int
    no_hallucination: int
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            self.correctness
            + self.completeness
            + self.anchoring
            + self.actionability
            + self.no_hallucination
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "correctness": self.correctness,
            "completeness": self.completeness,
            "anchoring": self.anchoring,
            "actionability": self.actionability,
            "no_hallucination": self.no_hallucination,
            "total": self.total,
        }

    def summary(self) -> str:
        return (
            f"quality {self.total}/25 "
            f"(correct {self.correctness}, complete {self.completeness}, "
            f"anchor {self.anchoring}, action {self.actionability}, "
            f"no-hallucination {self.no_hallucination})"
        )


def _score_correctness(steps: list[str], requirements: list[str]) -> int:
    """How many requirement keywords appear anywhere in the plan (0-5)."""
    if not requirements:
        return 5
    plan_text = " ".join(steps).lower()
    hits = sum(1 for req in requirements if _keyword_overlap(req, plan_text))
    frac = hits / len(requirements)
    return round(frac * 5)


def _score_completeness(steps: list[str], requirements: list[str]) -> int:
    """Fraction of requirements with a *dedicated* step addressing them (0-5)."""
    if not requirements:
        return 5
    covered = 0
    for req in requirements:
        if any(_keyword_overlap(req, step.lower()) for step in steps):
            covered += 1
    return round(covered / len(requirements) * 5)


def _keyword_overlap(requirement: str, text: str) -> bool:
    """True if a distinctive term from ``requirement`` appears in ``text``."""
    terms = [w for w in re.findall(r"[a-z0-9_]{4,}", requirement.lower())]
    return any(t in text for t in terms)


def _score_anchoring(anchors: list[Anchor]) -> int:
    """Map anchoring accuracy (0-1) to 0-5."""
    return round(anchoring_accuracy(anchors) * 5)


def _score_actionability(steps: list[str]) -> int:
    """Reward concrete action verbs, penalize vague filler (0-5)."""
    if not steps:
        return 0
    concrete = sum(1 for s in steps if _ACTION_VERB.search(s))
    vague = sum(1 for s in steps if _VAGUE.search(s))
    frac = (concrete - vague) / len(steps)
    return max(0, min(5, round(frac * 5)))


def _score_no_hallucination(anchors: list[Anchor]) -> int:
    """5 when no unresolved symbol-like references; degrade per offending step."""
    if not anchors:
        return 5
    offending = sum(1 for a in anchors if a.unresolved_terms)
    frac_clean = 1.0 - offending / len(anchors)
    return max(0, min(5, round(frac_clean * 5)))


def score_quality(
    steps: list[str],
    requirements: list[str],
    anchors: list[Anchor],
) -> QualityScore:
    """Score a plan on the 25-point rubric using deterministic evidence.

    ``steps`` are the plan steps, ``requirements`` the requirement atoms the plan
    should satisfy, and ``anchors`` the anchoring results for each step.
    """
    notes: list[str] = []
    correctness = _score_correctness(steps, requirements)
    completeness = _score_completeness(steps, requirements)
    anchoring = _score_anchoring(anchors)
    actionability = _score_actionability(steps)
    no_hallucination = _score_no_hallucination(anchors)

    if anchoring < 3:
        notes.append("weak anchoring: many steps lack verifiable file:line refs")
    if no_hallucination < 5:
        notes.append("possible hallucinated references detected")

    return QualityScore(
        correctness=correctness,
        completeness=completeness,
        anchoring=anchoring,
        actionability=actionability,
        no_hallucination=no_hallucination,
        notes=notes,
    )
