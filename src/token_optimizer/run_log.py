"""Per-run logging — write a complete, self-contained record of every run.

Each optimize/triage run writes one timestamped file under the log directory
(default ``logs/``) containing everything that happened: the source, the
resolved options and config, the token counts and savings, which stages fired,
the summary tier used, timing, cost, the output location, and any error.

Two artifacts are written per run:
  * ``<timestamp>_<kind>.log``  — a human-readable report
  * the same file ends with a ``--- JSON ---`` block holding the raw record, so
    logs are both readable and machine-parseable.

Secrets are never logged: API keys/tokens are recorded only as booleans
(``api_key_configured: true``), never their values.
"""

from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime
from typing import Any, Optional


def _app_version() -> str:
    try:
        from importlib.metadata import version

        return version("token-optimizer")
    except Exception:
        return "unknown"


def _now() -> datetime:
    return datetime.now()


def _safe_config(config: Any) -> dict[str, Any]:
    """Config snapshot with secrets reduced to booleans."""
    if config is None:
        return {}
    return {
        "model": getattr(config, "model", ""),
        "summary_model": getattr(config, "summary_model", ""),
        "local_model": getattr(config, "local_model", "") or "(none)",
        "local_model_url": getattr(config, "local_model_url", ""),
        "cache_dir": getattr(config, "cache_dir", ""),
        "log_dir": getattr(config, "log_dir", ""),
        "api_key_configured": bool(getattr(config, "anthropic_api_key", "")),
        "jira_configured": bool(getattr(config, "jira_api_token", "")),
        "github_configured": bool(getattr(config, "github_token", "")),
    }


def build_record(
    *,
    command: str,
    source: dict[str, Any],
    options: dict[str, Any],
    result: Any = None,
    config: Any = None,
    output_path: Optional[str] = None,
    error: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Assemble the full run record (a plain dict) from its parts.

    ``result`` is a ``TextOptimizationResult``/``OptimizationResult``-like object;
    whichever attributes exist are captured, so both pipelines can share this.
    """
    now = _now()
    record: dict[str, Any] = {
        "timestamp": now.isoformat(timespec="seconds"),
        "run_id": now.strftime("%Y%m%d_%H%M%S_%f"),
        "command": command,
        "status": "error" if error else "ok",
        "source": source,
        "options": options,
        "config": _safe_config(config),
        "environment": {
            "app_version": _app_version(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
    }

    if result is not None:
        metrics: dict[str, Any] = {}
        for attr in (
            "raw_tokens",
            "optimized_tokens",
            "tokens_saved",
            "reduction_pct",
            "token_method",
            "summary_tier",
            "duration_ms",
            "estimated_cost_usd",
        ):
            if hasattr(result, attr):
                metrics[attr] = getattr(result, attr)
        if hasattr(result, "stages"):
            metrics["stages"] = list(result.stages)
        if hasattr(result, "usage"):
            metrics["usage"] = result.usage
        # Text sizes (not the full text — that can be huge and may be sensitive).
        if hasattr(result, "raw_text"):
            metrics["raw_chars"] = len(result.raw_text)
        if hasattr(result, "optimized_text"):
            metrics["optimized_chars"] = len(result.optimized_text)
        record["metrics"] = metrics

    if output_path:
        record["output_path"] = output_path
    if error:
        record["error"] = error
    if extra:
        record["extra"] = extra
    return record


def _render(record: dict[str, Any]) -> str:
    """Human-readable report followed by a machine-parseable JSON block."""
    lines: list[str] = []
    w = lines.append
    w("=" * 72)
    w("TokenOptimizer — run log")
    w("=" * 72)
    w(f"Run ID    : {record['run_id']}")
    w(f"Timestamp : {record['timestamp']}")
    w(f"Command   : {record['command']}")
    w(f"Status    : {record['status'].upper()}")
    w("")

    w("- Source " + "-" * 63)
    for k, v in record.get("source", {}).items():
        w(f"  {k:16}: {v}")

    w("")
    w("- Options " + "-" * 62)
    for k, v in record.get("options", {}).items():
        w(f"  {k:16}: {v}")

    w("")
    w("- Config " + "-" * 63)
    for k, v in record.get("config", {}).items():
        w(f"  {k:20}: {v}")

    metrics = record.get("metrics")
    if metrics:
        w("")
        w("- Metrics " + "-" * 62)
        raw = metrics.get("raw_tokens")
        opt = metrics.get("optimized_tokens")
        saved = metrics.get("tokens_saved")
        pct = metrics.get("reduction_pct")
        if raw is not None and opt is not None:
            w(f"  tokens           : {raw} -> {opt}  (saved {saved}, {pct:.1f}% smaller)")
        w(f"  token_method     : {metrics.get('token_method')}")
        w(f"  summary_tier     : {metrics.get('summary_tier')}")
        w(f"  stages           : {', '.join(metrics.get('stages', [])) or 'none'}")
        if "raw_chars" in metrics:
            w(f"  chars            : {metrics.get('raw_chars')} -> {metrics.get('optimized_chars')}")
        if metrics.get("estimated_cost_usd") is not None:
            w(f"  est_cost_usd     : ${metrics.get('estimated_cost_usd'):.4f}")
        if metrics.get("duration_ms") is not None:
            w(f"  duration_ms      : {metrics.get('duration_ms'):.1f}")
        if "usage" in metrics:
            w(f"  usage            : {metrics['usage']}")

    w("")
    w("- Environment " + "-" * 58)
    for k, v in record.get("environment", {}).items():
        w(f"  {k:16}: {v}")

    if record.get("output_path"):
        w("")
        w(f"Output written to: {record['output_path']}")

    if record.get("error"):
        w("")
        w("- ERROR " + "-" * 64)
        w(f"  {record['error']}")

    w("")
    w("--- JSON ---")
    w(json.dumps(record, indent=2, default=str))
    w("")
    return "\n".join(lines)


def write_run_log(record: dict[str, Any], log_dir: str = "logs") -> str:
    """Write ``record`` to ``<log_dir>/<run_id>_<command>.log`` and return its path.

    Never raises — logging must not break a run. On failure it returns "".
    """
    try:
        os.makedirs(log_dir, exist_ok=True)
        safe_cmd = "".join(c if c.isalnum() else "-" for c in record.get("command", "run"))
        path = os.path.join(log_dir, f"{record['run_id']}_{safe_cmd}.log")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(_render(record))
        return path
    except Exception:
        return ""


def log_run(
    *,
    command: str,
    source: dict[str, Any],
    options: dict[str, Any],
    result: Any = None,
    config: Any = None,
    output_path: Optional[str] = None,
    error: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
    log_dir: Optional[str] = None,
) -> str:
    """Build and write a run log in one call; returns the log file path (or "")."""
    record = build_record(
        command=command,
        source=source,
        options=options,
        result=result,
        config=config,
        output_path=output_path,
        error=error,
        extra=extra,
    )
    directory = log_dir or getattr(config, "log_dir", "") or "logs"
    return write_run_log(record, directory)
