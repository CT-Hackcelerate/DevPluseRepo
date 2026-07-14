"""Evaluation harness — prove the cost/quality claims with A/B testing.

Runs a baseline (raw PRD → single premium model, no anchoring) against the
optimised pipeline (compressed PRD → anchored plan → routed models) over a set
of feature requests, and reports token, cost, and quality deltas.
"""

from .cost import PRICING, estimate_cost
from .quality_rubric import QualityScore, score_quality
from .ab_runner import ABResult, ABSummary, RunMetrics, run_ab_suite

__all__ = [
    "PRICING",
    "estimate_cost",
    "QualityScore",
    "score_quality",
    "ABResult",
    "ABSummary",
    "RunMetrics",
    "run_ab_suite",
]
