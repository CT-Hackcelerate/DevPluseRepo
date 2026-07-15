"""Focused offline tests for the codebase-anchoring skill (Skill 2a)."""

from pathlib import Path

from codebase_anchoring.anchor import anchor_plan, anchoring_accuracy
from codebase_anchoring.indexer import CodebaseIndex, build_index


def test_index_finds_python_symbols():
    root = str(Path(__file__).resolve().parents[2])  # repo root (spans src + skills)
    index = build_index(root)
    assert len(index) > 0
    hits = index.lookup("build_index")  # this skill's own function
    assert hits and hits[0].path.endswith("indexer.py") and hits[0].line > 0


def test_flags_hallucinated_symbol():
    index = CodebaseIndex(root=".")  # empty index
    anchors = anchor_plan(["Call totallyMadeUpFunction to do the thing"], index)
    assert not anchors[0].is_anchored
    assert "totallyMadeUpFunction" in anchors[0].unresolved_terms


def test_accuracy_is_a_fraction():
    index = CodebaseIndex(root=".")
    assert anchoring_accuracy([]) == 0.0
