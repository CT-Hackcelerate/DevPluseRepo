"""GitHub automations: token-optimized PR review and open-PR triage."""

from __future__ import annotations

from ..core.config import Config
from ..integrations.github import GitHubConnector
from ..optimize.compress import compress_diff
from ..optimize.pipeline import OptimizationResult, OptimizedRunner

_REVIEW_SYSTEM = (
    "You are a senior code reviewer. Review the pull request below and report:\n"
    "1. Correctness bugs or regressions (most important first).\n"
    "2. Security or data-loss risks.\n"
    "3. Missing tests or error handling for the changed code.\n"
    "Only report issues you can point to in the diff. Cite the file and a short "
    "snippet for each finding. If the PR looks safe to merge, say so plainly. "
    "Be concise — no restating the diff, no style nitpicks unless they cause bugs."
)

_PR_TRIAGE_SYSTEM = (
    "You are a repo maintainer triaging open pull requests. For each PR output one "
    "line: #<number> — <merge readiness: ready / needs-work / blocked>, the single "
    "most important reason, and a suggested reviewer area. Be terse and decisive."
)


def review_pr(
    config: Config,
    owner: str,
    repo: str,
    number: int,
    *,
    post_comment: bool = False,
    max_tokens: int = 3072,
) -> OptimizationResult:
    """Fetch a PR + its diff, compress the diff, and produce an optimized review.

    With ``post_comment=True`` the review is posted back as a PR comment.
    """
    with GitHubConnector(config) as gh:
        pr = gh.get_pr(owner, repo, number)
        diff = gh.get_pr_diff(owner, repo, number)

    # Diffs are the token sink — compress before the model sees them.
    pr["diff"] = compress_diff(diff, max_chars=16000)

    runner = OptimizedRunner(config)
    result = runner.run(
        system=_REVIEW_SYSTEM,
        task=f"Review pull request #{number} in {owner}/{repo}.",
        items=[pr],
        profile="github_pr",
        summarize=False,  # diff is already compressed; keep it verbatim for review
        max_tokens=max_tokens,
    )

    if post_comment:
        with GitHubConnector(config) as gh:
            gh.comment_on_issue(
                owner,
                repo,
                number,
                f"### Automated review (TokenOptimizer)\n\n{result.answer}",
            )

    return result


def triage_open_prs(
    config: Config,
    owner: str,
    repo: str,
    *,
    per_page: int = 30,
    include_diffs: bool = False,
) -> OptimizationResult:
    """Triage all open PRs in one optimized call.

    By default only PR metadata is used (cheap). Set ``include_diffs=True`` to pull
    and compress each diff for a deeper read — more tokens, better judgment.
    """
    with GitHubConnector(config) as gh:
        prs = gh.list_open_prs(owner, repo, per_page=per_page)
        if include_diffs:
            for pr in prs:
                diff = gh.get_pr_diff(owner, repo, pr["number"])
                pr["diff"] = compress_diff(diff, max_chars=6000)

    runner = OptimizedRunner(config)
    return runner.run(
        system=_PR_TRIAGE_SYSTEM,
        task=f"Triage the {len(prs)} open pull requests in {owner}/{repo}.",
        items=prs,
        profile="github_pr",
        summarize=include_diffs,  # summarize the larger diff-bearing payloads
        max_tokens=2048,
    )
