"""Strategy 1 — Local pre-filtering.

Rule-based extraction that runs *before* the LLM ever sees the data. The cheapest
possible token saving: keep only the fields relevant to the task and drop the rest
of a verbose API payload (JIRA issues and CI logs are mostly boilerplate).
"""

from __future__ import annotations

from typing import Any


# Field allowlists per task profile. Anything not listed is dropped before the
# payload is serialized for the LLM.
PREFILTER_PROFILES: dict[str, list[str]] = {
    "jira_issue": [
        "key",
        "summary",
        "description",
        "status",
        "priority",
        "issuetype",
        "labels",
        "components",
        "assignee",
        "reporter",
    ],
    "github_pr": [
        "number",
        "title",
        "body",
        "state",
        "labels",
        "user",
        "base",
        "head",
        "changed_files",
        "diff",
    ],
    "azdo_workitem": ["id", "title", "description", "state", "type", "tags", "assignedTo"],
    "gitlab_issue": ["iid", "title", "description", "state", "labels", "author"],
    "jenkins_build": ["number", "result", "duration", "displayName", "url", "console_log"],
}


def _pluck(obj: Any, keys: list[str]) -> Any:
    """Recursively keep only ``keys`` from dicts; simplify nested user objects."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k in keys:
            if k in obj:
                out[k] = _simplify(obj[k])
        return out
    return obj


def _simplify(value: Any) -> Any:
    """Collapse verbose nested objects (users, statuses) to their display value."""
    if isinstance(value, dict):
        for label_key in ("displayName", "name", "login", "value", "emailAddress"):
            if label_key in value:
                return value[label_key]
        return {k: _simplify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_simplify(v) for v in value]
    return value


def prefilter_fields(payload: dict[str, Any], profile: str) -> dict[str, Any]:
    """Reduce a raw API payload to only task-relevant fields.

    Unknown profiles pass the payload through unchanged so callers never crash on
    a typo — they just lose the saving.
    """
    keys = PREFILTER_PROFILES.get(profile)
    if not keys:
        return payload
    return _pluck(payload, keys)
