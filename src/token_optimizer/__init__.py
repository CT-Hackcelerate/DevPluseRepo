"""Token-optimized Claude automation. Document text is the default input source."""

from .core.config import Config
from .optimize.pipeline import OptimizedRunner, OptimizationResult
from .optimize.text_pipeline import (
    TextOptimizer,
    TextOptimizationResult,
    optimize_document,
    write_output,
)

__all__ = [
    "Config",
    "OptimizedRunner",
    "OptimizationResult",
    "TextOptimizer",
    "TextOptimizationResult",
    "optimize_document",
    "write_output",
]
__version__ = "0.2.0"
