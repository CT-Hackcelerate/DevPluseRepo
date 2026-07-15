"""JIRA Cloud REST API v3 connector."""

from __future__ import annotations

import base64
from typing import Any

from ..core.config import Config
from .base import Connector


def _adf_to_text(node: Any) -> str:
    """Flatten Atlassian Document Format (rich-text) to plain text."""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        return "".join(_adf_to_text(c) for c in node.get("content", []))
    if isinstance(node, list):
        return "".join(_adf_to_text(c) for c in node)
    return ""


class JiraConnector(Connector):
    def __init__(self, config: Config) -> None:
        config.require("jira_base_url", "jira_email", "jira_api_token")
        token = base64.b64encode(
            f"{config.jira_email}:{config.jira_api_token}".encode()
        ).decode()
        super().__init__(
            config.jira_base_url,
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def _normalize(self, issue: dict[str, Any]) -> dict[str, Any]:
        f = issue.get("fields", {})
        return {
            "key": issue.get("key"),
            "summary": f.get("summary"),
            "description": _adf_to_text(f.get("description")),
            "status": (f.get("status") or {}).get("name"),
            "priority": (f.get("priority") or {}).get("name"),
            "issuetype": (f.get("issuetype") or {}).get("name"),
            "labels": f.get("labels", []),
            "components": [c.get("name") for c in f.get("components", [])],
            "assignee": (f.get("assignee") or {}).get("displayName"),
            "reporter": (f.get("reporter") or {}).get("displayName"),
        }

    def get_issue(self, key: str) -> dict[str, Any]:
        raw = self.get(f"/rest/api/3/issue/{key}")
        return self._normalize(raw)

    def search(self, jql: str, max_results: int = 50) -> list[dict[str, Any]]:
        data = self.post(
            "/rest/api/3/search",
            json={
                "jql": jql,
                "maxResults": max_results,
                "fields": [
                    "summary", "description", "status", "priority",
                    "issuetype", "labels", "components", "assignee", "reporter",
                ],
            },
        )
        return [self._normalize(i) for i in data.get("issues", [])]

    def add_comment(self, key: str, body: str) -> dict[str, Any]:
        return self.post(
            f"/rest/api/3/issue/{key}/comment",
            json={
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": body}]}
                    ],
                }
            },
        )

    def transition(self, key: str, transition_id: str) -> None:
        self.post(
            f"/rest/api/3/issue/{key}/transitions",
            json={"transition": {"id": transition_id}},
        )
