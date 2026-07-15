"""Skill 2b — Complexity-based model routing.

Classifies each task by complexity (trivial / standard / complex) and routes it
to the cheapest model that can handle it, reserving premium models for genuine
reasoning. Rule-based + heuristic, with a confidence threshold that falls back to
the premium model whenever the classifier is unsure.
"""

from .classifier import Complexity, TaskClassification, classify_task
from .router import ModelRoute, RouterConfig, route_task

__all__ = [
    "Complexity",
    "TaskClassification",
    "classify_task",
    "ModelRoute",
    "RouterConfig",
    "route_task",
]
