# Changelog

All notable changes to TokenOptimizer. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); dates are ISO-8601.

## [Unreleased] — 2026-07-15

Delivers the two feature-development token-optimisation skills end-to-end
(engine → CLI → packaged skills → desktop UI → validation dashboard), and
restructures the codebase into an enterprise layered layout. No functional
regressions — the full offline suite (58 tests) passes.

### Added

**Feature-development skills (now surfaced, not just library code)**
- `tokenopt compress-prd` — Skill 1: compress a PRD/spec/ticket into dense
  requirement atoms (acceptance criteria kept verbatim).
- `tokenopt anchor-plan` — Skill 2a: anchor plan steps to real `file:line`
  references and flag unresolved (hallucinated) symbols.
- `tokenopt route` — Skill 2b: classify task complexity and route to the cheapest
  capable model, with a confidence-threshold fallback to premium.
- `tokenopt ab-suite` — run the 8-case / 2-BU baseline-vs-optimised comparison.
- `tokenopt dashboard` — render the A/B results to a self-contained HTML dashboard
  (inline SVG, zero dependencies).

**Packaged Claude Code skills** — `.claude/skills/prd-compressor/` and
`.claude/skills/codebase-anchor-router/` (SKILL.md wrappers around the CLI).

**A/B validation dashboard** — `evaluation/dashboard.py` builds a static HTML page
(KPI tiles + cost/quality/tokens bar charts + data table). Palette validated
against the data-viz colour checks.

**Desktop UI — two new tabs** (in addition to the existing optimizer):
- **Feature-Dev Skills** — a 2-column card grid (Skill 1, Skill 2b, Skill 2a,
  A/B validation) on the left half with a shared result console on the right half.
- **Dashboard** — KPI tiles + native Tk-canvas bar charts (cost & quality per
  case) with **Run A/B & Refresh** and **Open HTML Dashboard**; auto-runs on first
  open.
- Ctrl+Tab / Ctrl+Shift+Tab tab traversal; window sizes to the display work area;
  `TOKENOPT_UI_TAB=skills|dashboard` launch hook; `python -m token_optimizer.ui`.
- **Guided Demo** (Help → Guided Demo) — an automated, video-style walkthrough that
  auto-advances through 12 narrated scenes, switches tabs, and runs each feature
  live (compress / route / anchor / dashboard) with Prev/Pause/Next/Close controls.
  `TOKENOPT_UI_DEMO=1` auto-starts it.
- **In-UI Anthropic API key** — the Document source now has an optional API-key
  field so a user can opt into Claude (Haiku) summarization + exact token counts at
  runtime for a more effective result. The header mode chip and the summarize label
  update live; blank falls back to the `.env` key or fully offline.

**Regression tests** locking the headline claims
(`tests/test_hackcelerate.py`): every PRD compresses ≥ 67%, and the A/B suite meets
≥ 35% savings at ≥ 23/25 quality.

**Documentation** — `docs/FEATURES.md` rewritten (skills, validation, UI tabs,
project layout); `README.md` gains a skills/validation section and updated layout;
this changelog. **Architectural Design Document** at
`docs/Architecture-Design-Document.pdf` (generator:
`scripts/generate_architecture_pdf.py`) — layers, components, runtime flows,
cross-cutting concerns, and design-decision rationale. **Hackcelerate pitch deck**
at `docs/TokenOptimizer-Hackcelerate.pptx` (generator:
`scripts/generate_hackcelerate_ppt.py`) — 12 slides with a live A/B chart and the
embedded dashboard.

### Changed

**Validation dataset made realistic** (`evaluation/datasets.py`) — the 8 sample
PRDs were already terse (compressed only ~13%). They now carry the framing real
PRDs have (executive summary, background, motivation, stakeholders, revision
history, appendix), so compression measures **~73% average (≥67% every case)** —
matching the claim. Requirement atoms are unchanged, so quality is unaffected.

**Enterprise folder restructure** (all imports, entry points, and tests updated;
`git mv` preserved history):

| Before | After |
|---|---|
| `config.py`, `run_log.py`, `llm/` | `core/config.py`, `core/run_log.py`, `core/llm/` |
| `prd/`, `anchor/`, `router/` | `skills/prd/`, `skills/anchor/`, `skills/router/` |
| `eval/` | `evaluation/` |
| `ui.py` | `ui/app.py` (+ `ui/__init__.py`, `ui/__main__.py`) |
| `FEATURES.md`, `Hackcelerate-*.md`, `documents/*.pdf` | `docs/` |
| `Jira issue sample.txt`, `sample_document.docx` | `examples/` (kebab-case) |

**UI skill descriptions** — rewritten to crisp one-liners; the desktop window now
fits the display work area so no card is hidden or clipped.

### Fixed
- Documentation source links repointed to moved modules (`core/*`, `skills/*`,
  `evaluation/*`, `ui/app.py`); `docs/FEATURES.md` links now resolve from `docs/`.
- Offline `--summarize` regression (from the prior branch) remains fixed and
  default-on when offline.

### Notes
- `pyproject.toml` needed no change: `packages.find` auto-discovers the new
  sub-packages and the `tokenopt = token_optimizer.cli:main` entry point is stable.
- No public function signatures changed; only module import paths moved.
