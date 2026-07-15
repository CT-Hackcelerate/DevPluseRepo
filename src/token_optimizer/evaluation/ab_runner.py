"""A/B test harness — baseline vs optimised, over a suite of feature requests.

For each test case:

  * **Baseline (A):** raw PRD → single premium model, no anchoring. Input tokens
    are the full raw PRD; the plan is unanchored so quality loses the anchoring
    and hallucination points.
  * **Optimised (B):** compressed PRD → anchored plan → routed model. Input
    tokens are the compressed PRD; the plan is anchored against the repo index so
    quality gains the anchoring / no-hallucination points, and a cheaper model is
    used when the router allows.

The harness is deterministic and offline: it uses ``compress_prd`` for token
reduction, ``build_index`` + ``anchor_plan`` for anchoring, ``route_task`` for
model selection, and the 25-point rubric for quality — no network required. A
``plan_fn`` hook lets a real LLM be plugged in later without changing the harness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from codebase_anchoring.anchor import anchor_plan
from codebase_anchoring.indexer import CodebaseIndex
from prd_compression.compressor import compress_prd
from model_routing.router import RouterConfig, route_task
from .cost import estimate_cost
from .quality_rubric import QualityScore, score_quality

# A plan generator turns (requirements, task) into plan steps. The default is a
# deterministic offline stub; swap in an LLM-backed one for live runs.
PlanFn = Callable[[list[str], str], list[str]]


def _default_plan_fn(requirements: list[str], task: str) -> list[str]:
    """Offline stub: emit one actionable step per requirement atom.

    Real deployments pass a ``plan_fn`` that calls an LLM. For eval/demo we
    generate concrete, verb-led steps directly from the requirements so the
    harness runs with zero external dependencies.
    """
    steps: list[str] = []
    for req in requirements:
        steps.append(f"Implement: {req}")
    return steps


@dataclass
class RunMetrics:
    """Metrics captured for one arm (baseline or optimised) of a test case."""

    label: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    quality: QualityScore

    def summary(self) -> str:
        return (
            f"[{self.label}] model={self.model} in={self.input_tokens} "
            f"out={self.output_tokens} cost=${self.cost_usd:.5f} "
            f"{self.quality.summary()}"
        )


@dataclass
class ABResult:
    """Baseline vs optimised for a single test case."""

    name: str
    bu: str
    baseline: RunMetrics
    optimised: RunMetrics

    @property
    def cost_savings_pct(self) -> float:
        if self.baseline.cost_usd == 0:
            return 0.0
        return 100.0 * (self.baseline.cost_usd - self.optimised.cost_usd) / self.baseline.cost_usd

    @property
    def token_reduction_pct(self) -> float:
        if self.baseline.input_tokens == 0:
            return 0.0
        return 100.0 * (
            self.baseline.input_tokens - self.optimised.input_tokens
        ) / self.baseline.input_tokens

    @property
    def quality_delta(self) -> int:
        return self.optimised.quality.total - self.baseline.quality.total

    def summary(self) -> str:
        return (
            f"{self.name} ({self.bu}): "
            f"cost -{self.cost_savings_pct:.1f}%, "
            f"input tokens -{self.token_reduction_pct:.1f}%, "
            f"quality {self.baseline.quality.total}->{self.optimised.quality.total}/25"
        )


@dataclass
class ABSummary:
    """Aggregate results across the whole suite."""

    results: list[ABResult] = field(default_factory=list)

    @property
    def num_tests(self) -> int:
        return len(self.results)

    @property
    def bus(self) -> set[str]:
        return {r.bu for r in self.results}

    @property
    def avg_cost_savings_pct(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.cost_savings_pct for r in self.results) / len(self.results)

    @property
    def avg_token_reduction_pct(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.token_reduction_pct for r in self.results) / len(self.results)

    @property
    def avg_optimised_quality(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.optimised.quality.total for r in self.results) / len(self.results)

    @property
    def avg_baseline_quality(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.baseline.quality.total for r in self.results) / len(self.results)

    @property
    def total_tokens_saved(self) -> int:
        return sum(
            r.baseline.input_tokens - r.optimised.input_tokens for r in self.results
        )

    def summary(self) -> str:
        return (
            f"A/B suite: {self.num_tests} tests across {len(self.bus)} BUs\n"
            f"  avg cost savings:     {self.avg_cost_savings_pct:.1f}%\n"
            f"  avg input reduction:  {self.avg_token_reduction_pct:.1f}%\n"
            f"  total tokens saved:   {self.total_tokens_saved}\n"
            f"  avg quality:          baseline {self.avg_baseline_quality:.1f}/25 "
            f"-> optimised {self.avg_optimised_quality:.1f}/25"
        )


def _run_arm(
    *,
    label: str,
    model: str,
    input_tokens: int,
    steps: list[str],
    requirements: list[str],
    index: Optional[CodebaseIndex],
    output_tokens: int,
) -> RunMetrics:
    anchors = anchor_plan(steps, index) if index is not None else anchor_plan(steps, CodebaseIndex(root="."))
    quality = score_quality(steps, requirements, anchors)
    cost = estimate_cost(model, input_tokens, output_tokens)
    return RunMetrics(
        label=label,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        quality=quality,
    )


@dataclass
class TestCase:
    """One feature-request test case drawn from a BU."""

    name: str
    bu: str
    prd: str
    task: str


def run_ab_case(
    case: TestCase,
    index: CodebaseIndex,
    *,
    plan_fn: PlanFn = _default_plan_fn,
    router_config: Optional[RouterConfig] = None,
    baseline_model: str = "claude-opus-4-8",
    output_tokens: int = 800,
) -> ABResult:
    """Run one test case through both arms and return the comparison."""
    router_config = router_config or RouterConfig()

    # Compress the PRD → requirement atoms (used by both arms for a fair plan,
    # but baseline pays the full raw-token input cost).
    compression = compress_prd(case.prd)
    requirements = [a.text for a in compression.atoms]
    steps = plan_fn(requirements, case.task)

    # Baseline: full raw PRD tokens, premium model, NO anchoring index.
    baseline = _run_arm(
        label="baseline",
        model=baseline_model,
        input_tokens=compression.raw_tokens,
        steps=steps,
        requirements=requirements,
        index=None,
        output_tokens=output_tokens,
    )

    # Optimised: compressed PRD tokens, routed model, anchored plan.
    route = route_task(case.task, router_config)
    optimised = _run_arm(
        label="optimised",
        model=route.model,
        input_tokens=compression.compressed_tokens,
        steps=steps,
        requirements=requirements,
        index=index,
        output_tokens=output_tokens,
    )

    return ABResult(name=case.name, bu=case.bu, baseline=baseline, optimised=optimised)


def run_ab_suite(
    cases: list[TestCase],
    index: CodebaseIndex,
    *,
    plan_fn: PlanFn = _default_plan_fn,
    router_config: Optional[RouterConfig] = None,
) -> ABSummary:
    """Run the full A/B suite and aggregate the results."""
    summary = ABSummary()
    for case in cases:
        summary.results.append(
            run_ab_case(case, index, plan_fn=plan_fn, router_config=router_config)
        )
    return summary
