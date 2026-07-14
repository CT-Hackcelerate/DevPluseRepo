"""Offline tests for the deterministic optimization strategies (no API needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from token_optimizer.optimize.compress import (  # noqa: E402
    compress_diff,
    compress_prose,
    compress_text,
    dedupe_lines,
    head_tail_truncate,
    strip_noise,
)
from token_optimizer.optimize.prefilter import prefilter_fields  # noqa: E402
from token_optimizer.optimize.tokens import estimate_tokens  # noqa: E402
from token_optimizer.optimize.text_pipeline import TextOptimizer  # noqa: E402
from token_optimizer.integrations.document import read_document  # noqa: E402
from token_optimizer.config import Config  # noqa: E402
from token_optimizer.llm.cache import ResponseCache  # noqa: E402


def test_prefilter_keeps_only_allowlisted_fields():
    raw = {
        "key": "ABC-1",
        "summary": "boom",
        "assignee": {"displayName": "Jane", "emailAddress": "j@x.com"},
        "extra_noise": "x" * 1000,
        "customfield_99": [1, 2, 3],
    }
    out = prefilter_fields(raw, "jira_issue")
    assert set(out) <= {"key", "summary", "assignee"}
    assert out["assignee"] == "Jane"  # nested user collapsed to display name
    assert "extra_noise" not in out


def test_prefilter_unknown_profile_passthrough():
    raw = {"a": 1}
    assert prefilter_fields(raw, "does_not_exist") == raw


def test_strip_noise_keeps_errors_drops_info():
    log = "INFO starting\nDEBUG loading\nERROR boom happened\nINFO done"
    out = strip_noise(log)
    assert "ERROR boom happened" in out
    assert "INFO starting" not in out


def test_dedupe_collapses_repeats():
    out = dedupe_lines("same\nsame\nsame\nother")
    assert "(x3)" in out
    assert out.count("same") == 1


def test_head_tail_truncate():
    out = head_tail_truncate("A" * 100 + "B" * 100, max_chars=40)
    assert "omitted" in out
    assert len(out) < 200


def test_compress_reduces_size():
    log = ("INFO noise line\n" * 500) + "ERROR the real problem\n"
    out = compress_text(log, max_chars=5000)
    assert "ERROR the real problem" in out
    assert len(out) < len(log)


def test_compress_diff_keeps_changes_drops_context():
    diff = (
        "diff --git a/app.py b/app.py\n"
        "@@ -1,10 +1,10 @@\n"
        + "\n".join(f" context line {i}" for i in range(20))
        + "\n-old_value = 1\n+new_value = 2\n"
        + "\n".join(f" more context {i}" for i in range(20))
    )
    out = compress_diff(diff, max_chars=10000, context=2)
    assert "+new_value = 2" in out       # change kept
    assert "-old_value = 1" in out       # change kept
    assert "@@ -1,10 +1,10 @@" in out    # hunk header kept
    assert "unchanged lines" in out      # bulk context collapsed
    assert len(out) < len(diff)


def test_compress_prose_collapses_whitespace_and_blanks():
    text = "Hello    world\n\n\n\nHello    world\nUnique line"
    out = compress_prose(text, max_chars=10000)
    assert "Hello world" in out          # runs of spaces collapsed
    assert "\n\n\n" not in out           # blank runs squeezed
    assert "(x2)" in out                 # duplicate line deduped
    assert len(out) < len(text)


def test_estimate_tokens_scales_with_length():
    assert estimate_tokens("") == 0
    short = estimate_tokens("hello there friend")
    long = estimate_tokens("hello there friend " * 100)
    assert 0 < short < long


def test_read_document_plain_text(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("first line\nsecond line", encoding="utf-8")
    assert read_document(str(p)) == "first line\nsecond line"


def test_read_document_missing_file():
    import pytest

    with pytest.raises(FileNotFoundError):
        read_document("does-not-exist-12345.txt")


def test_text_optimizer_offline_compression():
    """No API key → compression only, tokens via local estimate."""
    cfg = Config(anthropic_api_key="")   # force offline path
    text = "Repeated line\n" * 50 + "The unique payload sentence."
    result = TextOptimizer(cfg).optimize(text, summarize=False)
    assert result.token_method == "estimate"
    assert result.optimized_tokens < result.raw_tokens
    assert result.reduction_pct > 0
    assert "The unique payload sentence." in result.optimized_text
    assert "compress" in result.stages


def test_build_config_overrides_and_falls_back():
    from token_optimizer.integrations.sources import build_config

    cfg = build_config(jira_base_url="https://x.atlassian.net", jira_email="")
    assert cfg.jira_base_url == "https://x.atlassian.net"
    # blank override must NOT clobber (falls back to env/default, here "")
    assert cfg.jira_email == Config().jira_email


def test_render_jira_issue_to_text():
    from token_optimizer.integrations.sources import _render_jira_issue

    issue = {
        "key": "ABC-1",
        "summary": "Boom",
        "status": "To Do",
        "priority": "High",
        "labels": ["payments"],
        "assignee": "Jane",
        "description": "It crashes.",
    }
    text = _render_jira_issue(issue)
    assert "ABC-1 — Boom" in text
    assert "status: To Do" in text
    assert "labels: payments" in text
    assert "It crashes." in text


def test_render_github_pr_to_text():
    from token_optimizer.integrations.sources import _render_pr

    pr = {"number": 42, "title": "Fix bug", "state": "open", "user": "octocat", "body": "Details"}
    text = _render_pr(pr, diff="diff --git a/x b/x\n@@ -1 +1 @@\n-a\n+b\n")
    assert "PR #42: Fix bug" in text
    assert "author: octocat" in text
    assert "DIFF:" in text
    assert "+b" in text


def test_response_cache_roundtrip(tmp_path):
    cache = ResponseCache(str(tmp_path))
    payload = {"model": "x", "messages": [{"role": "user", "content": "hi"}]}
    assert cache.get(payload) is None
    cache.set(payload, {"text": "hello"})
    assert cache.get(payload) == {"text": "hello"}


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
