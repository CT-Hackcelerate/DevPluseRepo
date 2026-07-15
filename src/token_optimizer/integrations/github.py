"""GitHub REST API connector."""

from __future__ import annotations

from typing import Any

from ..core.config import Config
from .base import Connector


class GitHubConnector(Connector):
    def __init__(self, config: Config) -> None:
        config.require("github_token")
        super().__init__(
            config.github_api_url,
            headers={
                "Authorization": f"Bearer {config.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    @staticmethod
    def _normalize_pr(pr: dict[str, Any]) -> dict[str, Any]:
        return {
            "number": pr.get("number"),
            "title": pr.get("title"),
            "body": pr.get("body") or "",
            "state": pr.get("state"),
            "labels": [l.get("name") for l in pr.get("labels", [])],
            "user": (pr.get("user") or {}).get("login"),
            "base": (pr.get("base") or {}).get("ref"),
            "head": (pr.get("head") or {}).get("ref"),
            "changed_files": pr.get("changed_files"),
        }

    def get_pr(self, owner: str, repo: str, number: int) -> dict[str, Any]:
        return self._normalize_pr(self.get(f"/repos/{owner}/{repo}/pulls/{number}"))

    def list_open_prs(self, owner: str, repo: str, per_page: int = 30) -> list[dict[str, Any]]:
        data = self.get(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": "open", "per_page": per_page},
        )
        return [self._normalize_pr(pr) for pr in data]

    def get_pr_diff(self, owner: str, repo: str, number: int) -> str:
        resp = self._client.get(
            f"/repos/{owner}/{repo}/pulls/{number}",
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        resp.raise_for_status()
        return resp.text

    def comment_on_issue(self, owner: str, repo: str, number: int, body: str) -> dict[str, Any]:
        return self.post(
            f"/repos/{owner}/{repo}/issues/{number}/comments", json={"body": body}
        )
