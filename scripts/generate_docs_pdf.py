"""Generate a detailed project-documentation PDF for TokenOptimizer.

Builds ``TokenOptimizer_Documentation.pdf`` at the project root using reportlab
(pure Python — no system dependencies). Run:

    python scripts/generate_docs_pdf.py [output.pdf]

The document content lives in ``build_story()`` below, so regenerating after a
docs change is just re-running this script.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "docs" / "TokenOptimizer_Documentation.pdf"

INK = colors.HexColor("#1a2233")
ACCENT = colors.HexColor("#0a5cff")
MUTED = colors.HexColor("#5b6472")
LIGHT = colors.HexColor("#eef2f8")
BORDER = colors.HexColor("#c7d0de")


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title2", parent=base["Title"], fontSize=30,
                                 textColor=INK, spaceAfter=6, leading=34),
        "subtitle": ParagraphStyle("Subtitle", parent=base["Normal"], fontSize=13,
                                   textColor=MUTED, alignment=TA_CENTER, leading=18),
        "meta": ParagraphStyle("Meta", parent=base["Normal"], fontSize=10,
                               textColor=MUTED, alignment=TA_CENTER),
        "h1": ParagraphStyle("H1", parent=base["Heading1"], fontSize=17,
                             textColor=ACCENT, spaceBefore=16, spaceAfter=6),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontSize=13,
                             textColor=INK, spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("Body2", parent=base["Normal"], fontSize=10.5,
                               textColor=INK, leading=15, spaceAfter=6, alignment=TA_LEFT),
        "bullet": ParagraphStyle("Bullet2", parent=base["Normal"], fontSize=10.5,
                                 textColor=INK, leading=14),
        "cell": ParagraphStyle("Cell", parent=base["Normal"], fontSize=9.5,
                               textColor=INK, leading=13),
        "cellhdr": ParagraphStyle("CellHdr", parent=base["Normal"], fontSize=9.5,
                                  textColor=colors.white, leading=13, fontName="Helvetica-Bold"),
        "code": ParagraphStyle("Code2", parent=base["Code"], fontSize=9,
                               textColor=INK, backColor=LIGHT, leading=13,
                               borderPadding=6, spaceBefore=4, spaceAfter=8),
        "toc": ParagraphStyle("Toc", parent=base["Normal"], fontSize=11,
                              textColor=INK, leading=20),
    }


def build_story(S: dict, meta: dict) -> list:
    story: list = []
    P = lambda t, s="body": Paragraph(t, S[s])  # noqa: E731

    def heading(text, style="h1"):
        story.append(Paragraph(text, S[style]))
        if style == "h1":
            story.append(HRFlowable(width="100%", thickness=1, color=BORDER,
                                    spaceBefore=2, spaceAfter=6))

    def bullets(items):
        story.append(ListFlowable(
            [ListItem(Paragraph(i, S["bullet"]), leftIndent=10) for i in items],
            bulletType="bullet", bulletColor=ACCENT, start="circle", leftIndent=14,
        ))
        story.append(Spacer(1, 6))

    def table(headers, rows, col_widths):
        data = [[Paragraph(h, S["cellhdr"]) for h in headers]]
        data += [[Paragraph(str(c), S["cell"]) for c in r] for r in rows]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 10))

    # ── Cover ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 5 * cm))
    story.append(Paragraph("TokenOptimizer", S["title"]))
    story.append(Paragraph("Project Documentation", S["subtitle"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "Token-optimized Claude automation — shrink text before it reaches the "
        "model, fully offline when needed.", S["subtitle"]))
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph(
        f"Version {meta['version']} &nbsp;•&nbsp; Generated {meta['date']}", S["meta"]))
    story.append(PageBreak())

    # ── Contents ───────────────────────────────────────────────────────
    heading("Contents")
    toc_items = [
        "1. Introduction & Purpose", "2. Key Capabilities", "3. Architecture Overview",
        "4. Optimization Strategies", "5. Summarization Tiers", "6. Token Counting",
        "7. Minimal Prompt Request", "8. Input Sources", "9. Interfaces",
        "10. Per-Run Logging", "11. Configuration", "12. Testing & Reliability",
        "13. Security Notes", "14. Getting Started",
    ]
    for it in toc_items:
        story.append(Paragraph(it, S["toc"]))
    story.append(PageBreak())

    # ── 1. Introduction ────────────────────────────────────────────────
    heading("1. Introduction &amp; Purpose")
    P_ = story.append
    P_(P("TokenOptimizer reduces the number of tokens sent to a Large Language "
         "Model, cutting cost and latency per call while preserving every fact a "
         "downstream agent needs. It points at a document, a JIRA issue, or a "
         "GitHub pull request, shrinks the text through a layered pipeline, and "
         "reports exactly how many tokens were saved."))
    P_(P("The central design goal is to <b>reduce LLM usage</b>. Because of that, "
         "the optimizer works <b>fully offline with no API key</b> — the deterministic "
         "and extractive strategies never call a cloud model. When a Claude API key "
         "or a local model is available, quality improves further, but it is never "
         "required."))

    # ── 2. Key capabilities ────────────────────────────────────────────
    heading("2. Key Capabilities")
    bullets([
        "Layered text reduction: deterministic cleanup, structure-aware extraction, and summarization.",
        "Works fully offline — no API key needed for real token savings.",
        "Three summarization tiers chosen automatically: Claude Haiku → local Ollama model → entity-anchored extractive.",
        "Accurate token counting via API, tiktoken (offline BPE), or a heuristic fallback.",
        "Desktop UI and command-line interface, plus a Windows launcher (run.bat).",
        "Detailed per-run logging with no secret leakage.",
        "Integrations: JIRA, GitHub, Jenkins, GitLab, Azure DevOps.",
    ])

    # ── 3. Architecture ────────────────────────────────────────────────
    heading("3. Architecture Overview")
    P_(P("Input text flows through the pipeline in "
         "<font face='Courier'>optimize/text_pipeline.py</font>. Each stage is "
         "skip-if-noop and only recorded when it actually changes the text:"))
    story.append(Paragraph(
        "raw text  →  deterministic reductions  →  summarization (optional tier)  "
        "→  whitespace/dedupe compression  →  optimized text + token report",
        S["code"]))
    bullets([
        "<b>Sources</b> (integrations/) turn documents/JIRA/GitHub into text.",
        "<b>optimize/local.py</b> — deterministic offline reductions.",
        "<b>optimize/local_model.py</b> — optional local Ollama summarizer.",
        "<b>optimize/tokens.py</b> — offline token counting.",
        "<b>run_log.py</b> — writes a full record of every run.",
    ])

    # ── 4. Optimization strategies ─────────────────────────────────────
    heading("4. Optimization Strategies")
    P_(P("Deterministic offline stages (always run; no API, no model):"))
    table(["Stage", "What it does"], [
        ["unicode", "Folds fancy Unicode to ASCII; strips zero-width chars and emoji."],
        ["framing", "Removes conversational/LLM packaging (preambles, sign-offs, follow-up offers)."],
        ["boilerplate", "Drops page numbers, headers/footers, rules, TOC dot leaders."],
        ["fields", "Collapses 'Label:'/value blocks into tight 'label: value'; drops placeholder fields."],
        ["punctuation", "Collapses decorative/repeated punctuation and bullet glyphs."],
        ["filler", "Substitutes verbose phrases with concise equivalents; deletes empty filler."],
        ["dedupe-paragraphs", "Removes near-duplicate paragraphs (normalized fingerprint)."],
        ["compress", "Collapses whitespace, dedupes repeated lines, head/tail-truncates."],
    ], [3.5 * cm, 12 * cm])

    # ── 5. Summarization tiers ─────────────────────────────────────────
    heading("5. Summarization Tiers")
    P_(P("Enabled with <font face='Courier'>--summarize</font> (or the UI checkbox). "
         "The best available tier is chosen automatically:"))
    table(["Tier", "Needs", "Quality"], [
        ["Claude Haiku", "ANTHROPIC_API_KEY", "Abstractive rewrite; highest quality."],
        ["Local Ollama model", "TOKENOPT_LOCAL_MODEL + running Ollama", "Abstractive, zero cloud tokens."],
        ["Entity-anchored extractive", "Nothing (pure offline)", "Keeps top sentences; never drops error codes, versions, IDs, paths, URLs."],
    ], [4.5 * cm, 6 * cm, 5 * cm])

    # ── 6. Token counting ──────────────────────────────────────────────
    heading("6. Token Counting")
    table(["Backend", "When used", "Reported as"], [
        ["API count_tokens", "API key configured", "api"],
        ["tiktoken (cl100k_base)", "tiktoken installed, no key", "tiktoken"],
        ["char/word heuristic", "fallback", "estimate"],
    ], [5.5 * cm, 6 * cm, 4 * cm])

    # ── 7. Minimal prompt ──────────────────────────────────────────────
    heading("7. Minimal Prompt Request")
    P_(P("<font face='Courier'>build_prompt_request()</font> assembles the smallest "
         "reasonable Messages-API request: a cached system prefix kept separate (so "
         "prompt caching stays hot), a terse task line, and the optimized data under "
         "one compact &lt;data&gt; delimiter — no repeated instructions, no padding."))

    # ── 8. Input sources ───────────────────────────────────────────────
    heading("8. Input Sources")
    bullets([
        "Documents — .docx (python-docx), .txt, .md, .log.",
        "JIRA — fetch issues by JQL query.",
        "GitHub — a single PR or all open PRs (optionally with diffs).",
        "Jenkins / GitLab / Azure DevOps — integration clients.",
        "Credentials come from the UI form or fall back to environment / .env.",
    ])

    # ── 9. Interfaces ──────────────────────────────────────────────────
    heading("9. Interfaces")
    P_(P("<b>Desktop UI</b> (<font face='Courier'>tokenopt ui</font>): Tkinter app with "
         "Document / JIRA / GitHub tabs. Auto-optimizes on load; shows Original vs "
         "Optimized panes and a token-review panel (Original / Optimized / Saved % / "
         "Counted-via)."))
    P_(P("<b>Command line</b>:"))
    table(["Command", "Purpose"], [
        ["optimize-doc --file F [--summarize]", "Optimize a document."],
        ["ui", "Launch the desktop UI."],
        ["triage-jira --jql Q [--max N]", "Triage JIRA issues."],
        ["triage-jenkins --job J [--build B]", "Root-cause a Jenkins failure."],
        ["review-github-pr --owner O --repo R --number N", "Review a pull request."],
        ["triage-github-prs --owner O --repo R [--diffs]", "Triage all open PRs."],
        ["demo", "Run on canned data."],
    ], [8.5 * cm, 7 * cm])
    P_(P("<b>Windows launcher</b>: <font face='Courier'>run.bat</font> — double-click "
         "to open the UI, or <font face='Courier'>run.bat &lt;command&gt;</font> from a "
         "terminal. Uses the project venv directly; no activation needed."))

    # ── 10. Logging ────────────────────────────────────────────────────
    heading("10. Per-Run Logging")
    P_(P("Every run writes one timestamped file to <font face='Courier'>logs/</font> "
         "(set via TOKENOPT_LOG_DIR). Each file has a human-readable report and a "
         "machine-parseable JSON block. Captured details:"))
    bullets([
        "Run ID, timestamp, command, status (ok / error).",
        "Source (file / JQL / PR) and resolved options.",
        "Config snapshot — secrets reduced to booleans (api_key_configured: true), never their values.",
        "Metrics: raw→optimized tokens, saved, reduction %, token_method, summary_tier, stages, char counts, cost, duration_ms.",
        "Environment: app version, Python version, platform.",
        "Output path and any error message.",
    ])
    P_(P("Logging never raises — a logging failure cannot break a run — and "
         "<font face='Courier'>logs/</font> is git-ignored."))

    # ── 11. Configuration ──────────────────────────────────────────────
    heading("11. Configuration")
    table(["Variable", "Default", "Purpose"], [
        ["ANTHROPIC_API_KEY", "—", "Enables Haiku summarization + exact token counts."],
        ["TOKENOPT_MODEL", "claude-opus-4-8", "Main reasoning model."],
        ["TOKENOPT_SUMMARY_MODEL", "claude-haiku-4-5", "Cheap summarization model."],
        ["TOKENOPT_LOCAL_MODEL", "—", "Ollama model for offline abstractive summary."],
        ["TOKENOPT_LOCAL_MODEL_URL", "localhost:11434", "Ollama server URL."],
        ["TOKENOPT_CACHE_DIR", ".tokenopt_cache", "Response cache location."],
        ["TOKENOPT_LOG_DIR", "logs", "Per-run log location."],
    ], [5.8 * cm, 4.2 * cm, 5.5 * cm])

    # ── 12. Testing ────────────────────────────────────────────────────
    heading("12. Testing &amp; Reliability")
    bullets([
        "Offline test suite (pytest tests/) covers every strategy — no network or API key required.",
        "Graceful degradation: no key → offline; no tiktoken → heuristic; Ollama down → extractive.",
        "Disk response cache serves repeated identical calls.",
        "No secret logging — verified by a dedicated test.",
    ])

    # ── 13. Security ───────────────────────────────────────────────────
    heading("13. Security Notes")
    bullets([
        "Keep real API keys only in .env (git-ignored), never in .env.example.",
        "Secrets never appear in run logs or optimized output.",
        "If a key is ever committed, revoke it immediately — history rewrites do not undo exposure.",
    ])

    # ── 14. Getting started ────────────────────────────────────────────
    heading("14. Getting Started")
    story.append(Paragraph(
        "python -m venv .venv<br/>"
        ".venv\\Scripts\\python.exe -m pip install -e .<br/>"
        ".venv\\Scripts\\python.exe -m pip install tiktoken   # optional: exact offline counts<br/>"
        "<br/>"
        "run.bat                                   # open the UI<br/>"
        "run.bat optimize-doc --file report.docx   # optimize a document<br/>"
        "run.bat optimize-doc --file notes.txt --summarize",
        S["code"]))
    P_(P("The offline optimizer needs no API key — pick a document in the UI or use "
         "<font face='Courier'>optimize-doc</font> and the token savings appear "
         "immediately. A detailed log is written to <font face='Courier'>logs/</font> "
         "for every run."))
    return story


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(2 * cm, 1.2 * cm, "TokenOptimizer — Project Documentation")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.setStrokeColor(BORDER)
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.restoreState()


def _app_version() -> str:
    try:
        from importlib.metadata import version
        return version("token-optimizer")
    except Exception:
        return "0.1.0"


def main(argv: list[str]) -> int:
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    S = _styles()
    meta = {"version": _app_version(), "date": datetime.now().strftime("%d %b %Y")}
    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
        title="TokenOptimizer — Project Documentation", author="TokenOptimizer",
    )
    doc.build(build_story(S, meta), onFirstPage=_footer, onLaterPages=_footer)
    print(f"PDF written to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
