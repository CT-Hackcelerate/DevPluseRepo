"""Generate the Architectural Design Document (ADD) PDF for TokenOptimizer.

Builds ``docs/Architecture-Design-Document.pdf`` using reportlab (pure Python —
no system dependencies). Run:

    python scripts/generate_architecture_pdf.py [output.pdf]

The document content lives in ``build_story()`` below, so regenerating after an
architecture change is just re-running this script.
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
    XPreformatted,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "docs" / "Architecture-Design-Document.pdf"

INK = colors.HexColor("#1a2233")
ACCENT = colors.HexColor("#0a5cff")
MUTED = colors.HexColor("#5b6472")
LIGHT = colors.HexColor("#eef2f8")
BORDER = colors.HexColor("#c7d0de")
DIAGRAM_BG = colors.HexColor("#f5f8fd")


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title2", parent=base["Title"], fontSize=28,
                                 textColor=INK, spaceAfter=6, leading=32),
        "subtitle": ParagraphStyle("Subtitle", parent=base["Normal"], fontSize=13,
                                   textColor=MUTED, alignment=TA_CENTER, leading=18),
        "meta": ParagraphStyle("Meta", parent=base["Normal"], fontSize=10,
                               textColor=MUTED, alignment=TA_CENTER),
        "h1": ParagraphStyle("H1", parent=base["Heading1"], fontSize=16,
                             textColor=ACCENT, spaceBefore=16, spaceAfter=6),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontSize=12.5,
                             textColor=INK, spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("Body2", parent=base["Normal"], fontSize=10.5,
                               textColor=INK, leading=15, spaceAfter=6, alignment=TA_LEFT),
        "bullet": ParagraphStyle("Bullet2", parent=base["Normal"], fontSize=10.5,
                                 textColor=INK, leading=14),
        "cell": ParagraphStyle("Cell", parent=base["Normal"], fontSize=9,
                               textColor=INK, leading=12),
        "cellhdr": ParagraphStyle("CellHdr", parent=base["Normal"], fontSize=9,
                                  textColor=colors.white, leading=12, fontName="Helvetica-Bold"),
        "code": ParagraphStyle("Code2", parent=base["Code"], fontSize=8.5,
                               textColor=INK, backColor=LIGHT, leading=12,
                               borderPadding=6, spaceBefore=4, spaceAfter=8),
        "diagram": ParagraphStyle("Diagram", parent=base["Code"], fontSize=8,
                                  textColor=INK, backColor=DIAGRAM_BG, leading=10.5,
                                  borderPadding=8, spaceBefore=4, spaceAfter=10,
                                  borderWidth=0.5, borderColor=BORDER),
        "toc": ParagraphStyle("Toc", parent=base["Normal"], fontSize=10.5,
                              textColor=INK, leading=18),
    }


def build_story(S: dict, meta: dict) -> list:
    story: list = []
    P = lambda t, s="body": Paragraph(t, S[s])  # noqa: E731

    def heading(text, style="h1"):
        story.append(Paragraph(text, S[style]))
        if style == "h1":
            story.append(HRFlowable(width="100%", thickness=1, color=BORDER,
                                    spaceBefore=2, spaceAfter=6))

    def para(t):
        story.append(P(t))

    def bullets(items):
        story.append(ListFlowable(
            [ListItem(Paragraph(i, S["bullet"]), leftIndent=10) for i in items],
            bulletType="bullet", bulletColor=ACCENT, start="circle", leftIndent=14,
        ))
        story.append(Spacer(1, 6))

    def diagram(text):
        story.append(XPreformatted(text, S["diagram"]))

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
    story.append(Spacer(1, 4.5 * cm))
    story.append(Paragraph("TokenOptimizer", S["title"]))
    story.append(Paragraph("Architectural Design Document", S["subtitle"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "Token-optimisation platform for AI-assisted development — layered, "
        "offline-first, and measurable.", S["subtitle"]))
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph(
        f"Version {meta['version']} &nbsp;•&nbsp; {meta['date']} &nbsp;•&nbsp; Status: Baseline",
        S["meta"]))
    story.append(PageBreak())

    # ── Document control ───────────────────────────────────────────────
    heading("Document Control")
    table(["Field", "Value"], [
        ["Title", "TokenOptimizer — Architectural Design Document"],
        ["Version", meta["version"]],
        ["Date", meta["date"]],
        ["Status", "Baseline"],
        ["Audience", "Engineers, architects, and reviewers"],
        ["Scope", "Full system: optimizer engine, feature-dev skills, interfaces, evaluation"],
        ["Related", "docs/FEATURES.md, docs/CHANGELOG.md, README.md"],
    ], [4 * cm, 12 * cm])

    heading("Contents")
    for it in [
        "1. Introduction &amp; Purpose",
        "2. Architectural Goals &amp; Constraints",
        "3. System Context",
        "4. Logical Architecture (Layered View)",
        "5. Component Responsibilities",
        "6. Feature-Development Skills",
        "7. Key Runtime Flows",
        "8. Cross-Cutting Concerns",
        "9. Evaluation &amp; Validation Architecture",
        "10. Deployment &amp; Runtime View",
        "11. Technology Stack",
        "12. Key Design Decisions (Rationale)",
        "13. Quality Attributes",
        "14. Directory Structure",
        "15. Risks &amp; Future Work",
    ]:
        story.append(Paragraph(it, S["toc"]))
    story.append(PageBreak())

    # ── 1. Introduction ────────────────────────────────────────────────
    heading("1. Introduction &amp; Purpose")
    para("TokenOptimizer reduces the number of tokens sent to a Large Language Model, "
         "cutting cost and latency per call while preserving every fact a downstream "
         "agent needs. Beyond a general text optimizer, it ships two "
         "<b>feature-development skills</b> — PRD compression and codebase anchoring + "
         "model routing — with an offline A/B suite that proves the cost/quality outcome.")
    para("This document describes the system's architecture: its layers, components, "
         "runtime flows, cross-cutting concerns, and the design decisions behind them. "
         "The guiding principle is <b>offline-first</b>: the deterministic strategies and "
         "both skills run with no API key; a Claude key or a local model only improves "
         "quality, and is never required.")

    # ── 2. Goals & constraints ─────────────────────────────────────────
    heading("2. Architectural Goals &amp; Constraints")
    story.append(P("<b>Goals</b>", "h2"))
    bullets([
        "Reduce LLM token spend measurably (input compression, routing, caching).",
        "Preserve decision-critical content — never silently drop facts or acceptance criteria.",
        "Work fully offline; degrade gracefully when optional dependencies are absent.",
        "Ground AI output in verifiable code (file:line) to eliminate hallucination rework.",
        "Be observable and reproducible: per-run logs and deterministic evaluation.",
    ])
    story.append(P("<b>Constraints</b>", "h2"))
    bullets([
        "Python 3.10+; minimal hard dependencies (anthropic, httpx, python-dotenv, python-docx).",
        "Desktop UI must be dependency-free (standard-library Tkinter only).",
        "No secrets in logs or output; credentials only via environment / .env.",
        "Optional extras: tiktoken (exact offline counts), reportlab (docs), Ollama (local model).",
    ])

    # ── 3. System context ──────────────────────────────────────────────
    heading("3. System Context")
    para("TokenOptimizer sits between a user (or automation) and external systems. "
         "Inputs are documents, JIRA issues, GitHub PRs, or PRDs; outputs are optimized "
         "text, anchored plans, routing decisions, run logs, and validation reports.")
    diagram(
        "        Documents / PRDs                 JIRA / GitHub / Jenkins / GitLab / AzDO\n"
        "                |                                        |\n"
        "                v                                        v\n"
        "     +-------------------------------------------------------------+\n"
        "     |                    T O K E N O P T I M I Z E R              |\n"
        "     |   CLI  |  Desktop UI  |  Packaged Claude Code skills        |\n"
        "     +-------------------------------------------------------------+\n"
        "                |                    |                   |\n"
        "                v                    v                   v\n"
        "     optimized_output.txt     Claude API (opt.)     logs/ + dashboards\n"
        "                              Ollama model (opt.)"
    )

    # ── 4. Logical architecture ────────────────────────────────────────
    heading("4. Logical Architecture (Layered View)")
    para("The package is organised into layers. Higher layers depend on lower ones; "
         "the <font face='Courier'>core</font> layer is depended upon by everything and "
         "depends on nothing else in the project.")
    diagram(
        "+---------------------------------------------------------------+\n"
        "|  INTERFACES     cli.py  |  ui/ (Tkinter)  |  .claude/skills/    |\n"
        "+---------------------------------------------------------------+\n"
        "|  SKILLS         skills/prd     skills/anchor     skills/router  |\n"
        "|  WORKFLOWS      automations/ (triage, review)                   |\n"
        "|  EVALUATION     evaluation/ (ab_runner, rubric, cost, dashboard)|\n"
        "+---------------------------------------------------------------+\n"
        "|  OPTIMIZE       local . compress . summarize . prefilter .      |\n"
        "|                 tokens . text/structured pipelines              |\n"
        "+---------------------------------------------------------------+\n"
        "|  INTEGRATIONS   jira . github . gitlab . jenkins . azdo . docs  |\n"
        "+---------------------------------------------------------------+\n"
        "|  CORE           config  .  run_log  .  llm (client + cache)     |\n"
        "+---------------------------------------------------------------+"
    )
    bullets([
        "<b>Core</b> — cross-cutting infrastructure: configuration, per-run logging, Claude client + response cache.",
        "<b>Integrations</b> — turn external systems and files into plain text.",
        "<b>Optimize</b> — the reduction strategies and the pipelines that compose them.",
        "<b>Skills / Workflows / Evaluation</b> — feature-dev skills, ready-made automations, and the A/B harness.",
        "<b>Interfaces</b> — CLI, desktop UI, and packaged Claude Code skills.",
    ])

    # ── 5. Component responsibilities ──────────────────────────────────
    heading("5. Component Responsibilities")
    table(["Package", "Responsibility"], [
        ["core/config.py", "Env-driven configuration (models, keys, cache/log dirs)."],
        ["core/run_log.py", "Write one structured, secret-free record per run."],
        ["core/llm/", "Claude client (count_tokens, adaptive thinking) + disk response cache."],
        ["optimize/", "Deterministic reductions, compression, summarization tiers, token counting, and the text/structured pipelines."],
        ["integrations/", "Connectors for JIRA, GitHub, GitLab, Jenkins, Azure DevOps, and documents."],
        ["automations/", "End-to-end flows: JIRA triage, Jenkins RCA, GitHub PR review/triage."],
        ["skills/prd/", "Skill 1 — compress a PRD into requirement atoms."],
        ["skills/anchor/", "Skill 2a — index a repo and anchor plan steps to file:line."],
        ["skills/router/", "Skill 2b — classify task complexity and route to a model."],
        ["evaluation/", "A/B runner, 25-point rubric, cost model, dataset, HTML dashboard."],
        ["ui/", "Tkinter desktop app (three tabs) — app.py, python -m entry."],
        ["cli.py", "The tokenopt command exposing every capability."],
    ], [4.4 * cm, 11.6 * cm])

    # ── 6. Feature-dev skills ──────────────────────────────────────────
    heading("6. Feature-Development Skills")
    story.append(P("<b>Skill 1 — PRD Compression</b> (skills/prd)", "h2"))
    para("Segments a PRD into units, classifies each into a requirement category "
         "(goal, acceptance-criteria, constraint, non-functional, dependency, "
         "out-of-scope), drops low-signal framing, and re-renders terse atoms. "
         "Acceptance criteria are preserved verbatim. ~67–73% input-token reduction.")
    story.append(P("<b>Skill 2a — Codebase Anchoring</b> (skills/anchor)", "h2"))
    para("Indexes a repository into a symbol table with exact file:line locations "
         "(AST for Python, regex for JS/TS/Java/Go/Ruby/C#) and resolves each plan "
         "step's symbol mentions to a real anchor. Unresolved symbol-like terms are "
         "flagged as possible hallucinations.")
    story.append(P("<b>Skill 2b — Model Routing</b> (skills/router)", "h2"))
    para("Classifies a task as trivial / standard / complex with a confidence score, "
         "then routes to haiku / sonnet / opus respectively. A confidence-threshold "
         "fallback upgrades one tier toward premium when the classifier is unsure, so a "
         "cheap model is never chosen on a coin-flip.")

    # ── 7. Runtime flows ───────────────────────────────────────────────
    heading("7. Key Runtime Flows")
    story.append(P("<b>7.1 Document / structured optimize flow</b>", "h2"))
    diagram(
        "raw text -> deterministic reductions -> summarization (optional tier)\n"
        "         -> whitespace/dedupe compress -> optimized text + token report -> log"
    )
    story.append(P("<b>7.2 Feature-development flow (the two skills + validation)</b>", "h2"))
    diagram(
        "PRD/spec --> compress_prd --> requirement atoms --> plan_fn(LLM) --> plan steps\n"
        "                                                          |\n"
        "   build_index(repo) ------> anchor_plan --------------->  + file:line anchors\n"
        "                                                          |\n"
        "   route_task(task) -------> model tier ---------------->  cheapest capable model\n"
        "                                                          |\n"
        "   score_quality + estimate_cost --> A/B metrics --> dashboard (HTML / native)"
    )

    # ── 8. Cross-cutting ───────────────────────────────────────────────
    heading("8. Cross-Cutting Concerns")
    table(["Concern", "Approach"], [
        ["Configuration", "core/config.py reads env / .env; blanks fall back to defaults."],
        ["Logging", "core/run_log.py writes a per-run report + JSON; never raises; secrets as booleans."],
        ["Caching", "core/llm/cache.py disk cache for identical calls; Claude native prompt cache for stable prefixes."],
        ["Token counting", "optimize/tokens.py: API count_tokens -> tiktoken -> heuristic."],
        ["Error handling", "Graceful degradation at every optional boundary; nothing hard-fails offline."],
        ["Security", "No secrets in logs or output; credentials only via env / .env."],
    ], [4 * cm, 12 * cm])

    # ── 9. Evaluation ──────────────────────────────────────────────────
    heading("9. Evaluation &amp; Validation Architecture")
    para("The evaluation package proves the cost/quality claims deterministically and "
         "offline. For each of 8 PRDs across 2 business units it runs a baseline arm "
         "(raw PRD -> premium model, no anchoring) against an optimised arm (compressed "
         "-> anchored -> routed) and scores both on a 25-point rubric.")
    bullets([
        "ab_runner.py — orchestrates both arms and aggregates deltas.",
        "quality_rubric.py — correctness, completeness, anchoring, actionability, no-hallucination.",
        "cost.py — tokens x per-model list price.",
        "datasets.py — 8 realistic verbose PRDs across Payments and Platform BUs.",
        "dashboard.py — self-contained HTML (inline SVG) rendered from the results.",
    ])
    para("<b>Validated, test-locked outcome:</b> ~73% average PRD compression, ~58% "
         "average cost savings, 24.0/25 average optimised quality (baseline 19.5).")

    # ── 10. Deployment & runtime ───────────────────────────────────────
    heading("10. Deployment &amp; Runtime View")
    bullets([
        "Installed as an editable package; the tokenopt console script is the primary entry point.",
        "Desktop UI: tokenopt ui or python -m token_optimizer.ui (Tkinter, no extra deps).",
        "Windows launcher run.bat wraps the venv for double-click or terminal use.",
        "Packaged Claude Code skills under .claude/skills/ wrap the CLI for agent use.",
        "Runs on a single machine; no server component. Optional network calls: Claude API, Ollama, integrations.",
    ])

    # ── 11. Technology stack ───────────────────────────────────────────
    heading("11. Technology Stack")
    table(["Area", "Choice"], [
        ["Language / runtime", "Python 3.10+"],
        ["Packaging", "setuptools src-layout; console_scripts entry point"],
        ["LLM SDK", "anthropic (Claude); Messages API + prompt caching"],
        ["HTTP", "httpx (integration connectors)"],
        ["Documents", "python-docx"],
        ["Token counting", "tiktoken (optional), API count_tokens, heuristic fallback"],
        ["Desktop UI", "Tkinter (standard library)"],
        ["Docs / PDF", "reportlab (optional extra)"],
        ["Local model", "Ollama HTTP server (optional)"],
        ["Testing", "pytest (offline, no API key)"],
    ], [4.8 * cm, 11.2 * cm])

    # ── 12. Design decisions ───────────────────────────────────────────
    heading("12. Key Design Decisions (Rationale)")
    table(["Decision", "Rationale"], [
        ["Offline-first pipeline", "Real token savings without a key; API/local model only improves quality."],
        ["core / skills separation", "Isolate cross-cutting infrastructure from product skills; clear dependency direction."],
        ["Deterministic skills & rubric", "Reproducible results and testable claims; no model-in-the-loop nondeterminism."],
        ["Confidence-threshold routing", "Under-powering a hard task costs more than the routing saved; upgrade when unsure."],
        ["Anchoring flags, not silently accepts", "Surfacing unresolved references eliminates hallucination-driven rework."],
        ["src-layout package", "Prevents accidental imports of the working tree; standard for distributable packages."],
        ["Self-contained HTML dashboard", "Zero runtime chart dependency; portable evidence for any stakeholder."],
        ["Skip-if-noop stages", "Reported stages reflect what actually changed the text; easier to reason about."],
    ], [5.4 * cm, 10.6 * cm])

    # ── 13. Quality attributes ─────────────────────────────────────────
    heading("13. Quality Attributes")
    bullets([
        "<b>Reliability</b> — graceful degradation at every optional boundary; logging can't break a run.",
        "<b>Security</b> — secrets never logged or emitted; credentials only via env / .env.",
        "<b>Testability</b> — 58 offline tests; headline claims locked by dedicated tests.",
        "<b>Performance / cost</b> — pre-filtering and compression are 0-token; routing and caching cut spend.",
        "<b>Maintainability</b> — layered packages, single-responsibility modules, relative imports.",
        "<b>Observability</b> — structured per-run logs (human + JSON) and an A/B dashboard.",
    ])

    # ── 14. Directory structure ────────────────────────────────────────
    heading("14. Directory Structure")
    diagram(
        "src/token_optimizer/\n"
        "  cli.py                 tokenopt command (all subcommands)\n"
        "  core/                  config . run_log . llm (client + cache)\n"
        "  skills/                prd (Skill 1) . anchor (2a) . router (2b)\n"
        "  optimize/              local . compress . summarize . prefilter .\n"
        "                         tokens . text/structured pipelines\n"
        "  integrations/          jira . github . gitlab . jenkins . azdo . docs\n"
        "  automations/           triage . github review\n"
        "  evaluation/            ab_runner . quality_rubric . cost . datasets .\n"
        "                         dashboard\n"
        "  ui/                    app.py (three-tab Tkinter app), __main__.py\n"
        "docs/                    FEATURES.md . CHANGELOG.md . this ADD . plan . PDFs\n"
        "examples/                sample PRD / document inputs\n"
        "tests/                   test_optimize.py . test_hackathon.py"
    )

    # ── 15. Risks & future work ────────────────────────────────────────
    heading("15. Risks &amp; Future Work")
    bullets([
        "PRD compression is tuned for PRD-shaped input; raw Jira bug tickets suit the structured pipeline better.",
        "The A/B plan generator is a deterministic stub; a live LLM plan_fn can be plugged in without harness changes.",
        "Regex symbol indexing (non-Python languages) is heuristic; a tree-sitter backend could improve accuracy.",
        "Cost figures use list prices; wire real usage metering for production dashboards.",
        "Consider persisting dashboards and trend history across runs for longitudinal reporting.",
    ])
    return story


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(2 * cm, 1.2 * cm, "TokenOptimizer — Architectural Design Document")
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
        title="TokenOptimizer — Architectural Design Document", author="TokenOptimizer",
    )
    doc.build(build_story(S, meta), onFirstPage=_footer, onLaterPages=_footer)
    print(f"PDF written to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
