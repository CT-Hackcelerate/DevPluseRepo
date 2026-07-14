"""Skill 2a — Codebase Anchoring.

Indexes a repository's symbols (functions, classes, methods) with their real
``file:line`` locations, then resolves plan steps to those verifiable anchors so
AI output never references a hallucinated path.
"""

from .indexer import CodeSymbol, CodebaseIndex, build_index
from .anchor import Anchor, anchor_plan, anchor_text

__all__ = [
    "CodeSymbol",
    "CodebaseIndex",
    "build_index",
    "Anchor",
    "anchor_plan",
    "anchor_text",
]
