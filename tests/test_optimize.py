"""Offline tests for the deterministic optimization strategies (no API needed)."""

import os
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
from token_optimizer.optimize.tokens import (  # noqa: E402
    count_tokens_offline,
    estimate_tokens,
)
from token_optimizer.optimize.local import (  # noqa: E402
    collapse_field_blocks,
    collapse_punctuation,
    dedupe_paragraphs,
    extractive_summary,
    normalize_unicode,
    reduce_text,
    split_sentences,
    strip_boilerplate,
    strip_conversational_framing,
    substitute_fillers,
)
from token_optimizer.optimize.text_pipeline import (  # noqa: E402
    TextOptimizer,
    build_prompt_request,
)
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


# ── Task C — offline token counting ─────────────────────────────────────────

def test_count_tokens_offline_reports_method():
    count, method = count_tokens_offline("hello there friend, how are you today?")
    assert count > 0
    assert method in {"tiktoken", "estimate"}


def test_count_tokens_offline_empty():
    count, _ = count_tokens_offline("")
    assert count == 0


# ── Task A — deterministic reductions ───────────────────────────────────────

def test_normalize_unicode_folds_fancy_chars():
    out = normalize_unicode("“Smart” quotes — and… done here")
    assert '"Smart"' in out
    assert "—" not in out and "-" in out
    assert "…" not in out and "..." in out
    assert " " not in out


def test_normalize_unicode_strips_emoji():
    out = normalize_unicode("Ship it \U0001f680 now")
    assert "\U0001f680" not in out
    assert "Ship it" in out


def test_strip_boilerplate_drops_page_and_rules():
    text = "Real content.\nPage 3 of 10\n=========\nMore content.\nConfidential"
    out = strip_boilerplate(text)
    assert "Real content." in out
    assert "More content." in out
    assert "Page 3 of 10" not in out
    assert "=========" not in out
    assert "Confidential" not in out


def test_collapse_punctuation():
    out = collapse_punctuation("Wow!!! Really??? Wait.......")
    assert "!!!" not in out and "!" in out
    assert "???" not in out and "?" in out
    assert "......." not in out


def test_substitute_fillers_shortens_phrases():
    out = substitute_fillers("We did this in order to win due to the fact that it helps.")
    assert "in order to" not in out.lower()
    assert "due to the fact that" not in out.lower()
    assert "to win" in out
    assert "because" in out


def test_dedupe_paragraphs_removes_near_duplicates():
    text = "The Cat Sat.\n\nSomething else.\n\nthe cat sat!\n\nFinal."
    out = dedupe_paragraphs(text)
    assert out.lower().count("the cat sat") == 1
    assert "Something else." in out
    assert "Final." in out


def test_strip_conversational_framing():
    text = (
        "Sure! Here's an example you could use.\n"
        "Summary: Login fails with 500 error.\n"
        "If you'd like, I can also create more templates.\n"
        "Would you like me to prepare those?"
    )
    out = strip_conversational_framing(text)
    assert "Summary: Login fails with 500 error." in out
    assert "Sure!" not in out
    assert "If you'd like" not in out
    assert "Would you like" not in out


def test_collapse_field_blocks_folds_labels_and_drops_placeholder():
    text = (
        "Summary:\n"
        "Login page throws error\n"
        "\n"
        "Priority:\n"
        "High\n"
        "\n"
        "Steps to Reproduce:\n"
        "Open login.\n"
        "\n"
        "Click submit.\n"
        "\n"
        "Assignee:\n"
        "[Leave blank or assign to backend developer]\n"
    )
    out = collapse_field_blocks(text)
    assert "Summary: Login page throws error" in out
    assert "Priority: High" in out
    assert "Steps to Reproduce: Open login.; Click submit." in out
    assert "Assignee" not in out            # placeholder-only field dropped
    assert "Leave blank" not in out
    assert len(out) < len(text)


def test_extractive_summary_anchors_must_keep_entities():
    # The version/error-code sentences must survive even though they'd score low.
    sentences = [
        "The team met on Monday to discuss the roadmap and goals for the quarter.",
        "Everyone agreed the roadmap looked good and the goals were clear.",
        "The build crashed with error 500 in checkout on app version v2.3.1.",
        "We had coffee and talked about the roadmap goals again afterwards.",
        "The roadmap goals were reviewed one final time before the meeting ended.",
    ]
    text = " ".join(sentences)
    summary = extractive_summary(text, ratio=0.2, min_sentences=1)
    assert "500" in summary            # error code anchored in
    assert "v2.3.1" in summary          # version anchored in


def test_reduce_text_reports_only_fired_stages():
    text = "Clean prose with nothing to reduce here."
    _, stages = reduce_text(text)
    assert stages == []  # nothing fired on already-clean text

    dirty = "Do this in order to win!!!\n\nPage 1 of 2\n\nDo this in order to win!!!"
    reduced, stages = reduce_text(dirty)
    assert "punctuation" in stages
    assert "filler" in stages
    assert len(reduced) < len(dirty)


# ── Task B — offline extractive summarization ───────────────────────────────

def test_split_sentences():
    sents = split_sentences("First one. Second one! Third one?")
    assert sents == ["First one.", "Second one!", "Third one?"]


def test_extractive_summary_keeps_subset_in_order():
    sentences = [
        "The payment service crashed with a null pointer exception on checkout.",
        "The weather today is quite nice and sunny outside.",
        "The null pointer exception occurs in the checkout payment handler.",
        "Someone brought donuts to the office this morning.",
        "Checkout payment failures spiked after the latest deploy.",
        "The cafeteria menu changed last week to add more options.",
    ]
    text = " ".join(sentences)
    summary = extractive_summary(text, ratio=0.5, min_sentences=2)
    assert len(summary) < len(text)
    # The payment/checkout sentences share distinctive terms → should rank in.
    assert "checkout" in summary.lower()


def test_extractive_summary_passthrough_when_short():
    text = "Only one sentence here."
    assert extractive_summary(text, min_sentences=3) == text


# ── Task D — minimal prompt request ─────────────────────────────────────────

def test_build_prompt_request_shape():
    req = build_prompt_request("some data", system="You are terse.", task="Summarize.")
    assert req["system"] == "You are terse."
    assert req["messages"][0]["role"] == "user"
    content = req["messages"][0]["content"]
    assert "Summarize." in content
    assert "<data>\nsome data\n</data>" in content


def test_build_prompt_request_omits_empty_system():
    req = build_prompt_request("data only")
    assert "system" not in req
    assert "<data>" in req["messages"][0]["content"]


def test_get_local_summarizer_none_when_unconfigured():
    from token_optimizer.optimize.local_model import get_local_summarizer

    assert get_local_summarizer("") is None  # no model configured → no local tier


def test_local_summarizer_unreachable_returns_none():
    from token_optimizer.optimize.local_model import LocalModelSummarizer

    # Point at a port nothing is listening on — must degrade, never raise.
    s = LocalModelSummarizer(model="nope", base_url="http://localhost:59999", timeout=1.0)
    assert s.available() is False
    assert s.summarize("some text") is None


def test_text_optimizer_offline_extractive_summarize():
    """No API key + summarize=True → offline extractive summary, still reduces."""
    cfg = Config(anthropic_api_key="")
    body = (
        "The payment service crashed with a null pointer exception on checkout. "
        "The weather today is quite nice and sunny outside. "
        "The null pointer exception occurs in the checkout payment handler. "
        "Someone brought donuts to the office this morning. "
        "Checkout payment failures spiked after the latest deploy. "
        "The cafeteria menu changed last week to add more options."
    )
    result = TextOptimizer(cfg).optimize(body, summarize=True, summary_ratio=0.5)
    assert "extractive-summarize" in result.stages
    assert result.optimized_tokens < result.raw_tokens


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
    assert result.token_method in {"tiktoken", "estimate"}  # offline, not API
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


def test_run_log_writes_file_with_details(tmp_path):
    from token_optimizer.run_log import build_record, write_run_log

    cfg = Config(anthropic_api_key="")
    text = "Repeated line\n" * 20 + "Unique payload."
    result = TextOptimizer(cfg).optimize(text, summarize=False)
    record = build_record(
        command="optimize-doc",
        source={"type": "document", "file": "x.txt"},
        options={"summarize": False},
        result=result,
        config=cfg,
        output_path="out.txt",
    )
    path = write_run_log(record, str(tmp_path))
    assert path and os.path.exists(path)
    content = Path(path).read_text(encoding="utf-8")
    # Human-readable report + machine-parseable JSON block both present.
    assert "TokenOptimizer — run log" in content
    assert "--- JSON ---" in content
    assert "raw_tokens" in content
    assert "duration_ms" in content
    assert record["metrics"]["raw_tokens"] == result.raw_tokens


def test_run_log_never_logs_secrets(tmp_path):
    from token_optimizer.run_log import build_record, write_run_log

    secret = "sk-ant-SECRET-VALUE-123"
    cfg = Config(anthropic_api_key=secret, jira_api_token="jira-secret", github_token="gh-secret")
    record = build_record(
        command="triage-jira",
        source={"type": "jira", "jql": "project = ABC"},
        options={},
        config=cfg,
    )
    path = write_run_log(record, str(tmp_path))
    content = Path(path).read_text(encoding="utf-8")
    assert secret not in content
    assert "jira-secret" not in content
    assert "gh-secret" not in content
    # But the fact that a key was configured IS recorded (as a boolean).
    assert record["config"]["api_key_configured"] is True


def test_run_log_records_error(tmp_path):
    from token_optimizer.run_log import build_record

    record = build_record(
        command="optimize-doc",
        source={"type": "document", "file": "missing.txt"},
        options={},
        error="FileNotFoundError: missing.txt",
    )
    assert record["status"] == "error"
    assert "FileNotFoundError" in record["error"]


def test_optimize_result_has_tier_and_duration():
    cfg = Config(anthropic_api_key="")
    body = (
        "The service crashed with error 500 in checkout. "
        "The weather is nice today outside. "
        "The checkout error 500 happens on the payment handler. "
        "Someone brought snacks to the office. "
        "Checkout payment failures rose after the deploy."
    )
    r = TextOptimizer(cfg).optimize(body, summarize=True, summary_ratio=0.5)
    assert r.summary_tier in {"extractive", "local-model"}
    assert r.duration_ms >= 0.0


def test_response_cache_roundtrip(tmp_path):
    cache = ResponseCache(str(tmp_path))
    payload = {"model": "x", "messages": [{"role": "user", "content": "hi"}]}
    assert cache.get(payload) is None
    cache.set(payload, {"text": "hello"})
    assert cache.get(payload) == {"text": "hello"}


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
