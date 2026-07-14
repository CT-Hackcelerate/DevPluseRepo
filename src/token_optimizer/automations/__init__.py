"""Ready-made automations built on the optimizer + connectors."""

from .triage import triage_jira, triage_jenkins_failure
from .github import review_pr, triage_open_prs

__all__ = [
    "triage_jira",
    "triage_jenkins_failure",
    "review_pr",
    "triage_open_prs",
]
