"""Jenkins REST API connector."""

from __future__ import annotations

from typing import Any

from ..config import Config
from .base import Connector


class JenkinsConnector(Connector):
    def __init__(self, config: Config) -> None:
        config.require("jenkins_base_url", "jenkins_user", "jenkins_api_token")
        super().__init__(
            config.jenkins_base_url,
            auth=(config.jenkins_user, config.jenkins_api_token),
            headers={"Accept": "application/json"},
        )

    def get_build(self, job: str, number: int | str = "lastBuild") -> dict[str, Any]:
        data = self.get(f"/job/{job}/{number}/api/json")
        return {
            "number": data.get("number"),
            "result": data.get("result"),
            "duration": data.get("duration"),
            "displayName": data.get("displayName"),
            "url": data.get("url"),
        }

    def get_console_log(self, job: str, number: int | str = "lastBuild") -> str:
        """Fetch the raw console output — the big, noisy input compression targets."""
        resp = self._client.get(f"/job/{job}/{number}/consoleText")
        resp.raise_for_status()
        return resp.text

    def list_jobs(self) -> list[dict[str, Any]]:
        data = self.get("/api/json", params={"tree": "jobs[name,color,url]"})
        return data.get("jobs", [])

    def trigger_build(self, job: str) -> None:
        self.post(f"/job/{job}/build")
