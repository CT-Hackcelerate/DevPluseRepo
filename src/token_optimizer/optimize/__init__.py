"""Token-reduction strategies and the pipeline that composes them."""

from .prefilter import prefilter_fields, PREFILTER_PROFILES
from .compress import compress_text, compress_diff, compress_prose, dedupe_lines, strip_noise
from .summarize import summarize_if_large
from .tokens import estimate_tokens
from .pipeline import OptimizedRunner, OptimizationResult
from .text_pipeline import (
    TextOptimizer,
    TextOptimizationResult,
    optimize_document,
    write_output,
)

__all__ = [
    "prefilter_fields",
    "PREFILTER_PROFILES",
    "compress_text",
    "compress_diff",
    "compress_prose",
    "dedupe_lines",
    "strip_noise",
    "summarize_if_large",
    "estimate_tokens",
    "OptimizedRunner",
    "OptimizationResult",
    "TextOptimizer",
    "TextOptimizationResult",
    "optimize_document",
    "write_output",
]
