"""Example automations that wire connectors into the optimized runner."""

from __future__ import annotations

from ..config import Config
from ..integrations.jenkins import JenkinsConnector
from ..integrations.jira import JiraConnector
from ..optimize.compress import compress_text
from ..optimize.pipeline import OptimizationResult, OptimizedRunner

_TRIAGE_SYSTEM = (
    "You are a senior engineering triage assistant. For each item you are given, "
    "decide: (1) priority (P0-P3), (2) the most likely area/component, and (3) a "
    "one-line next action. Be terse and decisive. Output one block per item, "
    "prefixed with its identifier."
)

_RCA_SYSTEM = (
    "You are a CI/CD failure analyst. Given a build's console log, identify the "
    "root cause in one sentence, the failing step, and a concrete fix. Ignore "
    "warnings unless they are the cause. Be concise."
)


def triage_jira(config: Config, jql: str, max_results: int = 25) -> OptimizationResult:
    """Pull JIRA issues matching ``jql`` and triage them in a single optimized call."""
    with JiraConnector(config) as jira:
        issues = jira.search(jql, max_results=max_results)

    runner = OptimizedRunner(config)
    return runner.run(
        system=_TRIAGE_SYSTEM,
        task=f"Triage these {len(issues)} JIRA issues.",
        items=issues,
        profile="jira_issue",
        summarize=True,
    )


def triage_jenkins_failure(config: Config, job: str, number: int | str = "lastBuild") -> OptimizationResult:
    """Fetch a Jenkins console log, compress it hard, and get a root-cause analysis."""
    with JenkinsConnector(config) as jenkins:
        build = jenkins.get_build(job, number)
        log = jenkins.get_console_log(job, number)

    # Console logs are the worst offenders: compress aggressively before the LLM.
    build["console_log"] = compress_text(log, max_chars=8000, keep_errors=True)

    runner = OptimizedRunner(config)
    return runner.run(
        system=_RCA_SYSTEM,
        task=f"Analyze the failure of Jenkins job '{job}' build {build.get('number')}.",
        items=[build],
        profile="jenkins_build",  # console_log is in this profile's allowlist
        summarize=True,
        max_tokens=2048,
    )
