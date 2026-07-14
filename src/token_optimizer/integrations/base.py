"""Shared HTTP plumbing for connectors."""

from __future__ import annotations

from typing import Any, Optional

import httpx


class Connector:
    """Base class wrapping an ``httpx.Client`` with sane defaults."""

    def __init__(
        self,
        base_url: str,
        *,
        headers: Optional[dict[str, str]] = None,
        auth: Optional[tuple[str, str]] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers or {},
            auth=auth,
            timeout=timeout,
        )

    def get(self, path: str, **kwargs: Any) -> Any:
        resp = self._client.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def post(self, path: str, **kwargs: Any) -> Any:
        resp = self._client.post(path, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def put(self, path: str, **kwargs: Any) -> Any:
        resp = self._client.put(path, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Connector":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
