"""Local, on-disk response cache.

This is the *client-side* half of the caching strategy: identical (model, system,
messages, params) requests are answered from disk without hitting the API at all —
0 tokens spent. Claude's own prompt caching (server-side, ~90% cheaper reads)
handles the case where the prefix is stable but the tail varies; see
``ClaudeClient`` for that.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional


def _stable_key(payload: dict[str, Any]) -> str:
    """Deterministic hash of a request payload (sorted keys → stable bytes)."""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class ResponseCache:
    cache_dir: str
    ttl_seconds: Optional[float] = 24 * 3600  # None = never expire

    def __post_init__(self) -> None:
        os.makedirs(self.cache_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def get(self, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
        key = _stable_key(payload)
        path = self._path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                record = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None
        if self.ttl_seconds is not None and (time.time() - record.get("_ts", 0)) > self.ttl_seconds:
            return None
        return record.get("value")

    def set(self, payload: dict[str, Any], value: dict[str, Any]) -> None:
        key = _stable_key(payload)
        record = {"_ts": time.time(), "value": value}
        tmp = self._path(key) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)
        os.replace(tmp, self._path(key))
