"""Remote sources — fetch text from JIRA and GitHub (Git) for optimization.

These helpers turn a live connection into the same plain text the document reader
produces, so the optimizer and UI can treat JIRA issues and GitHub pull requests
exactly like a Word document: fetch → text → optimize → token review.

Credentials come from a :class:`~token_optimizer.core.config.Config`. ``build_config``
lets the UI override the env/.env values with fields typed into the connection form.
"""

from __future__ import annotations

from typing import Any

from ..core.config import Config


def build_config(**overrides: str) -> Config:
    """Return a Config from env/.env, overridden by any non-empty ``overrides``."""
    cfg = Config()
    for key, value in overrides.items():
        if value not in (None, ""):
            setattr(cfg, key, value)
    return cfg


# ── JIRA ────────────────────────────────────────────────────────────
def _render_jira_issue(it: dict[str, Any]) -> str:
    lines = [f"{it.get('key')} — {it.get('summary', '')}".strip()]
    meta = [f"{k}: {it[k]}" for k in ("status", "priority", "issuetype") if it.get(k)]
    if meta:
        lines.append(" | ".join(meta))
    if it.get("labels"):
        lines.append("labels: " + ", ".join(str(x) for x in it["labels"]))
    if it.get("components"):
        lines.append("components: " + ", ".join(str(x) for x in it["components"] if x))
    who = [f"{k}: {it[k]}" for k in ("assignee", "reporter") if it.get(k)]
    if who:
        lines.append(" | ".join(who))
    if it.get("description"):
        lines.append("\n" + str(it["description"]))
    return "\n".join(lines)


def fetch_jira_text(config: Config, jql: str, max_results: int = 25) -> tuple[str, int]:
    """Search JIRA with ``jql`` and return (rendered text, issue count)."""
    from .jira import JiraConnector

    with JiraConnector(config) as jc:
        issues = jc.search(jql, max_results=max_results)
    text = "\n\n---\n\n".join(_render_jira_issue(i) for i in issues)
    return text, len(issues)


# ── GitHub (Git) ──────────────────────────────────────────────────────
def _render_pr(pr: dict[str, Any], diff: str = "") -> str:
    lines = [f"PR #{pr.get('number')}: {pr.get('title', '')}".strip()]
    meta = []
    for label, key in (("state", "state"), ("author", "user"), ("base", "base"), ("head", "head")):
        if pr.get(key):
            meta.append(f"{label}: {pr[key]}")
    if meta:
        lines.append(" | ".join(meta))
    if pr.get("labels"):
        lines.append("labels: " + ", ".join(str(x) for x in pr["labels"] if x))
    if pr.get("body"):
        lines.append("\n" + str(pr["body"]))
    if diff:
        from ..optimize.compress import compress_diff

        lines.append("\n\nDIFF:\n" + compress_diff(diff))
    return "\n".join(lines)


def fetch_github_text(
    config: Config,
    owner: str,
    repo: str,
    number: int | None = None,
    *,
    include_diff: bool = False,
) -> tuple[str, int]:
    """Fetch from GitHub and return (rendered text, PR count).

    If ``number`` is given, fetch that one PR (optionally with its diff). Otherwise
    list the repo's open PRs and render each.
    """
    from .github import GitHubConnector

    with GitHubConnector(config) as gh:
        if number:
            pr = gh.get_pr(owner, repo, number)
            diff = gh.get_pr_diff(owner, repo, number) if include_diff else ""
            return _render_pr(pr, diff), 1
        prs = gh.list_open_prs(owner, repo)
    text = "\n\n---\n\n".join(_render_pr(pr) for pr in prs)
    return text, len(prs)
