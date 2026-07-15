"""GitLab REST API v4 connector."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..core.config import Config
from .base import Connector


class GitLabConnector(Connector):
    def __init__(self, config: Config) -> None:
        config.require("gitlab_token")
        super().__init__(
            config.gitlab_base_url,
            headers={
                "PRIVATE-TOKEN": config.gitlab_token,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    @staticmethod
    def _project(path: str) -> str:
        # GitLab accepts URL-encoded "group/project" as the project id.
        return quote(path, safe="")

    @staticmethod
    def _normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
        return {
            "iid": issue.get("iid"),
            "title": issue.get("title"),
            "description": issue.get("description") or "",
            "state": issue.get("state"),
            "labels": issue.get("labels", []),
            "author": (issue.get("author") or {}).get("name"),
        }

    def get_issue(self, project: str, iid: int) -> dict[str, Any]:
        raw = self.get(f"/api/v4/projects/{self._project(project)}/issues/{iid}")
        return self._normalize_issue(raw)

    def list_issues(self, project: str, state: str = "opened", per_page: int = 30) -> list[dict[str, Any]]:
        data = self.get(
            f"/api/v4/projects/{self._project(project)}/issues",
            params={"state": state, "per_page": per_page},
        )
        return [self._normalize_issue(i) for i in data]

    def get_mr_changes(self, project: str, mr_iid: int) -> dict[str, Any]:
        return self.get(
            f"/api/v4/projects/{self._project(project)}/merge_requests/{mr_iid}/changes"
        )

    def comment_on_issue(self, project: str, iid: int, body: str) -> dict[str, Any]:
        return self.post(
            f"/api/v4/projects/{self._project(project)}/issues/{iid}/notes",
            json={"body": body},
        )
