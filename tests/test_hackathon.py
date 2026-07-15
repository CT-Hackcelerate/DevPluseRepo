"""Offline tests for the Hackathon token-optimisation skills (no API needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from token_optimizer.skills.prd.compressor import compress_prd, render_atoms  # noqa: E402
from token_optimizer.skills.anchor.indexer import build_index, CodebaseIndex  # noqa: E402
from token_optimizer.skills.anchor.anchor import anchor_plan, anchoring_accuracy  # noqa: E402
from token_optimizer.skills.router.classifier import Complexity, classify_task  # noqa: E402
from token_optimizer.skills.router.router import RouterConfig, route_task  # noqa: E402
from token_optimizer.evaluation.cost import estimate_cost  # noqa: E402
from token_optimizer.evaluation.quality_rubric import score_quality  # noqa: E402
from token_optimizer.evaluation.ab_runner import TestCase, run_ab_suite  # noqa: E402
from token_optimizer.evaluation.datasets import sample_cases  # noqa: E402
from token_optimizer.evaluation.dashboard import build_dashboard  # noqa: E402


_SAMPLE_PRD = """
Executive Summary

This document, basically, restates a lot of background context. As mentioned, it
is very important. Please note that this is verbose on purpose.

Requirements

- The system must automatically retry a failed charge up to 3 times.
- Each retry must be idempotent so a customer is never double-charged.
- Acceptance criteria: Given a transient error, when a charge fails, then the
  system should retry with the same idempotency key.
- Performance: retries must complete within 30 seconds.

Out of scope

- We will not change the refund flow.
"""


# ── Skill 1 — PRD compression ────────────────────────────────────────────────

def test_compress_prd_reduces_tokens():
    result = compress_prd(_SAMPLE_PRD)
    assert result.compressed_tokens < result.raw_tokens
    assert result.reduction_pct > 0
    assert len(result.atoms) > 0


def test_compress_prd_preserves_acceptance_criteria_verbatim():
    result = compress_prd(_SAMPLE_PRD)
    ac = [a for a in result.atoms if a.category == "acceptance-criteria"]
    assert ac, "expected at least one acceptance-criteria atom"
    # The exact phrasing of the criterion is kept (not paraphrased).
    assert "idempotency key" in " ".join(a.text for a in ac)


def test_compress_prd_drops_framing_prose():
    result = compress_prd(_SAMPLE_PRD)
    text = result.compressed_text.lower()
    assert "restates a lot of background" not in text
    assert result.dropped_units > 0


def test_render_atoms_groups_by_category():
    result = compress_prd(_SAMPLE_PRD)
    rendered = render_atoms(result.atoms)
    assert "## GOALS" in rendered or "## ACCEPTANCE CRITERIA" in rendered


# ── Skill 2a — codebase anchoring ────────────────────────────────────────────

def test_build_index_finds_python_symbols():
    root = str(Path(__file__).resolve().parents[1] / "src")
    index = build_index(root)
    assert len(index) > 0
    # A known function from this repo should be indexed.
    hits = index.lookup("compress_prd")
    assert hits, "compress_prd should be indexed"
    assert hits[0].path.endswith("compressor.py")
    assert hits[0].line > 0


def test_anchor_plan_resolves_real_symbols():
    root = str(Path(__file__).resolve().parents[1] / "src")
    index = build_index(root)
    steps = [
        "Call compress_prd on the raw PRD text",
        "Use build_index to index the repository",
    ]
    anchors = anchor_plan(steps, index)
    assert all(a.is_anchored for a in anchors)
    assert anchoring_accuracy(anchors) == 1.0


def test_anchor_plan_flags_hallucinated_symbol():
    index = CodebaseIndex(root=".")  # empty index
    anchors = anchor_plan(["Call totallyMadeUpFunction to do the thing"], index)
    assert not anchors[0].is_anchored
    assert "totallyMadeUpFunction" in anchors[0].unresolved_terms


# ── Skill 2b — routing ───────────────────────────────────────────────────────

def test_classify_trivial_task():
    result = classify_task("rename a variable and fix a typo")
    assert result.complexity == Complexity.TRIVIAL


def test_classify_complex_task():
    result = classify_task(
        "Redesign the authentication architecture to handle concurrency and "
        "avoid race conditions with a distributed transaction"
    )
    assert result.complexity == Complexity.COMPLEX


def test_route_trivial_goes_cheap():
    cfg = RouterConfig()
    route = route_task("rename the config variable to snake_case", cfg)
    assert route.model == cfg.trivial_model


def test_route_complex_goes_premium():
    cfg = RouterConfig()
    route = route_task(
        "Design a distributed transaction protocol with rollback and idempotency",
        cfg,
    )
    assert route.model == cfg.complex_model


def test_low_confidence_upgrades_model():
    cfg = RouterConfig()  # default threshold 0.5
    # Ambiguous task: one trivial cue ("rename") + one standard cue ("implement")
    # ties the signal, damping confidence below the threshold → safety upgrade.
    route = route_task("implement rename", cfg)
    assert route.confidence < cfg.confidence_threshold
    assert route.upgraded
    assert route.model != cfg.trivial_model



# ── Eval — cost, rubric, A/B ─────────────────────────────────────────────────

def test_estimate_cost_scales_and_ranks_models():
    cheap = estimate_cost("claude-haiku-4-5", 1000, 1000)
    premium = estimate_cost("claude-opus-4-8", 1000, 1000)
    assert 0 < cheap < premium


def test_score_quality_perfect_when_anchored_and_complete():
    root = str(Path(__file__).resolve().parents[1] / "src")
    index = build_index(root)
    requirements = ["compress the PRD", "build the index"]
    steps = [
        "Implement compress_prd to compress the PRD",
        "Implement build_index to build the index",
    ]
    anchors = anchor_plan(steps, index)
    score = score_quality(steps, requirements, anchors)
    assert score.total <= 25
    assert score.anchoring >= 3  # real anchors present


def test_ab_suite_shows_savings_and_maintains_quality():
    root = str(Path(__file__).resolve().parents[1] / "src")
    index = build_index(root)
    summary = run_ab_suite(sample_cases(), index)
    assert summary.num_tests >= 8
    assert len(summary.bus) >= 2
    # Optimised arm should cost less and not lose quality overall.
    assert summary.avg_cost_savings_pct > 0
    assert summary.avg_optimised_quality >= summary.avg_baseline_quality
    assert summary.total_tokens_saved > 0


# ── Headline claims — lock them so a dataset/pipeline change can't quietly
#    regress the numbers we present to the client. ──────────────────────────

def test_prd_compression_meets_67_percent_claim():
    """Skill 1 headline: PRD input compressed by ~67% across the suite."""
    raw = comp = 0
    for case in sample_cases():
        result = compress_prd(case.prd)
        raw += result.raw_tokens
        comp += result.compressed_tokens
        # Every individual PRD should clear the bar, not just the average.
        assert result.reduction_pct >= 67.0, f"{case.name}: {result.reduction_pct:.1f}%"
    overall = 100.0 * (raw - comp) / raw
    assert overall >= 67.0, f"overall compression {overall:.1f}% < 67%"


def test_ab_suite_meets_savings_and_quality_targets():
    """Validated outcome: up to 35% savings at quality >= 23/25 over 2 BUs."""
    root = str(Path(__file__).resolve().parents[1] / "src")
    index = build_index(root)
    summary = run_ab_suite(sample_cases(), index)
    assert summary.num_tests >= 8
    assert len(summary.bus) >= 2
    assert summary.avg_cost_savings_pct >= 35.0
    assert summary.avg_optimised_quality >= 23.0
    assert summary.avg_optimised_quality >= summary.avg_baseline_quality


def test_dashboard_builds_valid_html_with_real_numbers():
    root = str(Path(__file__).resolve().parents[1] / "src")
    html = build_dashboard(root)
    assert html.startswith("<!DOCTYPE html>")
    # Three inline-SVG charts + a data table, no external assets.
    assert html.count("<svg") == 3
    assert "table" in html and "<tr>" in html
    assert "http://" not in html and "https://" not in html  # fully self-contained
    # Real KPI values are injected (not template placeholders).
    assert "{kpis}" not in html and "{cost_chart}" not in html
    assert "/ 25" in html


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
