"""Skill 1 — PRD Compression.

Compresses a verbose Product Requirement Document into a dense, structured set
of decision-relevant "requirement atoms" before it reaches the LLM, targeting
~67% input-token reduction with no loss of decision-critical content.
"""

from .compressor import (
    PRDCompressionResult,
    RequirementAtom,
    compress_prd,
    render_atoms,
)

__all__ = [
    "PRDCompressionResult",
    "RequirementAtom",
    "compress_prd",
    "render_atoms",
]
