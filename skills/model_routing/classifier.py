"""Task complexity classifier — rule-based + heuristic, with a confidence score.

Classifies a task description into one of three complexity tiers:

  * ``TRIVIAL``  — formatting, renaming, boilerplate, simple lookups.
  * ``STANDARD`` — ordinary feature work / bug fixes.
  * ``COMPLEX``  — architecture, concurrency, security, multi-system reasoning.

The classifier is deterministic: it scores the task against keyword signals for
each tier and a few structural heuristics (length, multi-step language). It
returns a ``confidence`` in [0,1]; the router uses a threshold to fall back to
the premium model when the signal is weak, so a cheap model is never chosen on a
coin-flip.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Complexity(str, Enum):
    TRIVIAL = "trivial"
    STANDARD = "standard"
    COMPLEX = "complex"


# Keyword cues per tier. Weighted so a strong single cue (e.g. "rename") counts.
_TRIVIAL_CUES = [
    "rename", "format", "reformat", "indent", "lint", "typo", "spelling",
    "rename variable", "add comment", "docstring", "boilerplate", "getter",
    "setter", "import", "sort", "capitalize", "lowercase", "uppercase",
    "list files", "find the", "look up", "grep", "what is", "where is",
    "add a field", "add field", "constant", "enum value",
]
_COMPLEX_CUES = [
    "architecture", "refactor", "redesign", "concurrency", "thread", "race condition",
    "distributed", "migration", "schema change", "security", "authentication",
    "authorization", "encryption", "performance", "optimize", "scalab",
    "algorithm", "state machine", "transaction", "consistency", "deadlock",
    "design a", "trade-off", "tradeoff", "backwards compatible", "rollback",
    "multi-tenant", "idempoten", "eventual consistency", "cache invalidation",
]
_STANDARD_CUES = [
    "implement", "add feature", "fix bug", "endpoint", "api", "handler",
    "validate", "form", "component", "test", "integrate", "update", "parse",
]

_MULTI_STEP = re.compile(r"\b(and then|after that|first|second|finally|multiple|several steps)\b", re.IGNORECASE)


@dataclass
class TaskClassification:
    task: str
    complexity: Complexity
    confidence: float
    signals: dict[str, int] = field(default_factory=dict)

    def render(self) -> str:
        return f"{self.complexity.value} (confidence {self.confidence:.2f})"


def _count_cues(text: str, cues: list[str]) -> int:
    return sum(1 for cue in cues if cue in text)


def classify_task(task: str) -> TaskClassification:
    """Classify ``task`` into a complexity tier with a confidence score."""
    text = task.lower()

    trivial = _count_cues(text, _TRIVIAL_CUES)
    standard = _count_cues(text, _STANDARD_CUES)
    complex_ = _count_cues(text, _COMPLEX_CUES)

    # Structural heuristics.
    word_count = len(text.split())
    if word_count > 60:
        complex_ += 1
    if _MULTI_STEP.search(text):
        complex_ += 1
    if word_count <= 8 and trivial == 0 and complex_ == 0:
        # Very short, no strong cues → likely a simple lookup/tweak.
        trivial += 1

    scores = {
        Complexity.TRIVIAL: trivial,
        Complexity.STANDARD: standard,
        Complexity.COMPLEX: complex_,
    }
    total = trivial + standard + complex_

    # Complexity dominates: any strong complex signal wins outright — the cost of
    # under-powering a hard task (wrong answer, regeneration) dwarfs the savings.
    if complex_ >= 2 or (complex_ >= 1 and complex_ >= trivial):
        winner = Complexity.COMPLEX
    else:
        winner = max(scores, key=lambda k: scores[k])

    if total == 0:
        # No signal at all → default to STANDARD with low confidence.
        return TaskClassification(
            task=task,
            complexity=Complexity.STANDARD,
            confidence=0.3,
            signals={k.value: v for k, v in scores.items()},
        )

    # Confidence = winner's share of total signal, lightly damped by ambiguity.
    confidence = scores[winner] / total
    # If two tiers tie closely, damp confidence so the router can fall back.
    sorted_scores = sorted(scores.values(), reverse=True)
    if len(sorted_scores) >= 2 and sorted_scores[0] == sorted_scores[1] and sorted_scores[0] > 0:
        confidence *= 0.6

    return TaskClassification(
        task=task,
        complexity=winner,
        confidence=round(confidence, 3),
        signals={k.value: v for k, v in scores.items()},
    )
