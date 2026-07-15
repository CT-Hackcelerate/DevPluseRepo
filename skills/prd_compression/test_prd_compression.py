"""Focused offline tests for the PRD-compression skill (Skill 1)."""

from prd_compression.compressor import compress_prd, render_atoms

_PRD = """
Executive Summary

This document restates background at length. As mentioned, it is important.

Requirements

- The system must automatically retry a failed charge up to 3 times.
- Each retry must be idempotent.
- Acceptance criteria: Given a transient error, when a charge fails, then the
  system should retry with the same idempotency key.

Out of scope

- We will not change the refund flow.
"""


def test_compresses_and_reduces_tokens():
    r = compress_prd(_PRD)
    assert r.compressed_tokens < r.raw_tokens
    assert r.reduction_pct > 0
    assert len(r.atoms) > 0


def test_keeps_acceptance_criteria_verbatim():
    r = compress_prd(_PRD)
    assert "idempotency key" in " ".join(a.text for a in r.atoms)


def test_render_groups_by_category():
    r = compress_prd(_PRD)
    rendered = render_atoms(r.atoms)
    assert "## GOALS" in rendered or "## ACCEPTANCE CRITERIA" in rendered
