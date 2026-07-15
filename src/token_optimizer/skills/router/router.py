"""Model router — pick the cheapest capable model for a task's complexity tier.

Maps complexity tiers to concrete models and applies the confidence-threshold
fallback: if the classifier isn't confident enough that a task is cheap, the
router upgrades to the premium model rather than risk a low-quality answer that
would cost more in regeneration than it saved.

Model tiers use the same names as ``llm.client._PRICING`` so cost estimates line
up with the rest of the system.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .classifier import Complexity, TaskClassification, classify_task


@dataclass
class RouterConfig:
    """Which model serves each tier, and the confidence needed to go cheap."""

    trivial_model: str = "claude-haiku-4-5"
    standard_model: str = "claude-sonnet-5"
    complex_model: str = "claude-opus-4-8"
    # Below this confidence, upgrade one tier toward premium (safety first).
    confidence_threshold: float = 0.5

    def model_for(self, tier: Complexity) -> str:
        return {
            Complexity.TRIVIAL: self.trivial_model,
            Complexity.STANDARD: self.standard_model,
            Complexity.COMPLEX: self.complex_model,
        }[tier]


@dataclass
class ModelRoute:
    """The routing decision for a task."""

    task: str
    complexity: Complexity
    confidence: float
    model: str
    upgraded: bool = False  # True if the confidence fallback bumped the tier
    classification: TaskClassification | None = field(default=None, repr=False)

    def render(self) -> str:
        note = "  (upgraded: low confidence)" if self.upgraded else ""
        return (
            f"'{self.task[:50]}...' -> {self.complexity.value} "
            f"-> {self.model}{note}"
        )


# Tier escalation order: trivial < standard < complex.
_ESCALATE = {
    Complexity.TRIVIAL: Complexity.STANDARD,
    Complexity.STANDARD: Complexity.COMPLEX,
    Complexity.COMPLEX: Complexity.COMPLEX,
}


def route_task(task: str, config: RouterConfig | None = None) -> ModelRoute:
    """Classify ``task`` and choose the model, applying the confidence fallback."""
    config = config or RouterConfig()
    result = classify_task(task)

    tier = result.complexity
    upgraded = False
    # Low confidence on a cheap tier → escalate one step toward premium.
    if result.confidence < config.confidence_threshold and tier != Complexity.COMPLEX:
        tier = _ESCALATE[tier]
        upgraded = True

    return ModelRoute(
        task=task,
        complexity=tier,
        confidence=result.confidence,
        model=config.model_for(tier),
        upgraded=upgraded,
        classification=result,
    )
