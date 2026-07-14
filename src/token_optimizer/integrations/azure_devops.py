"""Azure DevOps REST API connector (Boards work items + Pipelines builds)."""

from __future__ import annotations

import base64
from typing import Any

from ..config import Config
from .base import Connector

_API = "api-version=7.1"


class AzureDevOpsConnector(Connector):
    def __init__(self, config: Config) -> None:
        config.require("azdo_org_url", "azdo_project", "azdo_pat")
        # AzDO PAT auth: empty username, PAT as password, Basic-encoded.
        token = base64.b64encode(f":{config.azdo_pat}".encode()).decode()
        super().__init__(
            config.azdo_org_url,
            headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
        )
        self.project = config.azdo_project

    @staticmethod
    def _normalize_wi(wi: dict[str, Any]) -> dict[str, Any]:
        f = wi.get("fields", {})
        return {
            "id": wi.get("id"),
            "title": f.get("System.Title"),
            "description": f.get("System.Description", ""),
            "state": f.get("System.State"),
            "type": f.get("System.WorkItemType"),
            "tags": f.get("System.Tags", ""),
            "assignedTo": (f.get("System.AssignedTo") or {}).get("displayName")
            if isinstance(f.get("System.AssignedTo"), dict)
            else f.get("System.AssignedTo"),
        }

    def get_work_item(self, wid: int) -> dict[str, Any]:
        raw = self.get(f"/{self.project}/_apis/wit/workitems/{wid}?{_API}")
        return self._normalize_wi(raw)

    def query_work_items(self, wiql: str, top: int = 50) -> list[dict[str, Any]]:
        """Run a WIQL query, then batch-fetch the referenced work items."""
        result = self.post(
            f"/{self.project}/_apis/wit/wiql?{_API}", json={"query": wiql}
        )
        ids = [w["id"] for w in result.get("workItems", [])][:top]
        if not ids:
            return []
        batch = self.post(
            f"/_apis/wit/workitemsbatch?{_API}",
            json={
                "ids": ids,
                "fields": [
                    "System.Title", "System.Description", "System.State",
                    "System.WorkItemType", "System.Tags", "System.AssignedTo",
                ],
            },
        )
        return [self._normalize_wi(w) for w in batch.get("value", [])]

    def list_recent_builds(self, top: int = 20) -> list[dict[str, Any]]:
        data = self.get(f"/{self.project}/_apis/build/builds?{_API}&$top={top}")
        return [
            {
                "id": b.get("id"),
                "result": b.get("result"),
                "status": b.get("status"),
                "definition": (b.get("definition") or {}).get("name"),
                "url": b.get("_links", {}).get("web", {}).get("href"),
            }
            for b in data.get("value", [])
        ]
