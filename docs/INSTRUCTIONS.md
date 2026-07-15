# TokenOptimizer — Instructions & Run Guide

How to install, run, and demo **TokenOptimizer**, plus a complete catalogue of
every document, slide deck, demo video, and diagram shipped with the project.

- **Platform:** Windows 11 (a `run.bat` launcher is provided); works on any OS with Python.
- **Python:** 3.10+
- **Works fully offline** — no API key required. An Anthropic key is optional and only
  unlocks Claude summarization + exact token counts.

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | `python --version` |
| pip / venv | Bundled with Python |
| (Optional) Anthropic API key | Unlocks Claude Haiku summarization & exact token counts |
| (Optional) Ollama | Local abstractive summarization, zero cloud tokens |
| (Optional) `reportlab`, `python-pptx` | Only to regenerate the PDFs / pitch deck |
| (Optional) Java + `plantuml-1.2026.6.jar` | Only to regenerate the `.puml` diagrams |

---

## 2. First-time setup

From the project root (`c:\Users\VasanthJoelS\Desktop\TokenOptimizer`):

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
```

Optional extras:

```bat
REM Real BPE token counting offline
.venv\Scripts\python.exe -m pip install -e ".[tokenize]"

REM Tooling to regenerate docs/PDF/PPTX
.venv\Scripts\python.exe -m pip install -e ".[docs]"
```

Optional configuration — copy `.env.example` to `.env` and fill in what you need
(everything is optional; blank = fully offline):

```
ANTHROPIC_API_KEY=sk-ant-...        # optional: Claude summarization + exact tokens
TOKENOPT_MODEL=claude-opus-4-8      # main reasoning model
TOKENOPT_SUMMARY_MODEL=claude-haiku-4-5
TOKENOPT_LOCAL_MODEL=               # optional: Ollama model, e.g. llama3.2
```

---

## 3. Running the app

### Easiest — double-click `run.bat`

- **Double-click `run.bat`** → opens the desktop UI.
- Or from a terminal, pass any `tokenopt` command through it:

```bat
run.bat                                       REM opens the desktop UI
run.bat optimize-doc --file report.docx
run.bat optimize-doc --file notes.txt --summarize
run.bat demo
```

`run.bat` uses the project's `.venv` directly — no activation needed.

### Directly via the CLI (any OS)

```bat
.venv\Scripts\python.exe -m token_optimizer.cli <command> [options]
REM or, since the package installs a console script:
tokenopt <command> [options]
```

### Desktop UI

```bat
tokenopt ui
REM or:  python -m token_optimizer.ui
```

Useful launch hooks (environment variables):

| Variable | Effect |
|---|---|
| `TOKENOPT_UI_TAB=skills` | Open on the Feature-Dev Skills tab |
| `TOKENOPT_UI_TAB=dashboard` | Open on the Dashboard tab |
| `TOKENOPT_UI_DEMO=1` | Auto-start the narrated Guided Demo |

The UI has three tabs — **Optimizer**, **Feature-Dev Skills**, **Dashboard** — plus
**Help → Guided Demo** (an automated, voice-over walkthrough of every feature).

---

## 4. CLI command reference

Run `tokenopt <command> --help` for full options.

### Document optimization
| Command | What it does |
|---|---|
| `optimize-doc --file <path> [--summarize] [--out <file>]` | Optimize a `.docx/.txt/.md` document's tokens. `--summarize` adds Claude Haiku (needs API key). Default output: `optimized_output.txt`. |
| `ui` | Open the desktop document-optimizer UI. |
| `demo` | Run the optimizer on canned sample data. |

### Feature-development skills
| Command | Skill |
|---|---|
| `compress-prd --file <path> [--out <file>]` | **Skill 1** — compress a verbose PRD into dense requirement atoms (acceptance criteria kept verbatim). Default output: `compressed_prd.txt`. |
| `anchor-plan --plan <file> [--repo <dir>]` | **Skill 2a** — anchor plan steps (one per line) to real `file:line` references; flag hallucinated symbols. |
| `route --task "<description>"` | **Skill 2b** — classify task complexity and route to the cheapest capable model. |

### A/B validation
| Command | What it does |
|---|---|
| `ab-suite [--repo <dir>]` | Run the 8-case / 2-BU A/B suite (baseline vs optimised). Default repo: `src`. |
| `dashboard [--repo <dir>] [--out <file>]` | Render A/B results to a self-contained HTML dashboard. Default output: `ab_dashboard.html`. |

### DevOps automations
| Command | What it does |
|---|---|
| `triage-jira --jql "<query>" [--max N]` | Triage JIRA issues matching a JQL query. |
| `triage-jenkins --job <name> [--build <id>]` | Root-cause a Jenkins build failure. |
| `review-github-pr --owner <o> --repo <r> --number <n> [--post-comment]` | Review a single GitHub pull request. |
| `triage-github-prs --owner <o> --repo <r> [--diffs]` | Triage all open PRs in a repo. |

> DevOps commands read credentials from `.env` (JIRA / GitHub / Azure DevOps / GitLab / Jenkins).

### A 60-second demo path

```bat
tokenopt compress-prd --file examples\jira-issue-sample.txt
tokenopt route --task "rename a variable across the module"
tokenopt anchor-plan --plan my_plan.txt --repo src
tokenopt ab-suite
tokenopt dashboard        REM then open ab_dashboard.html
```

Or just run the UI and use **Help → Guided Demo**.

---

## 5. Running the tests

```bat
.venv\Scripts\python.exe -m pytest
```

The full offline suite (**68 tests**, `tests/` + each skill's own tests) passes with
no API key and no network.

---

## 6. Available documents, deck & demo files

All shipped artefacts live under `docs/` (plus samples in `examples/`).

### 6.1 Documents (`docs/`)

| File | Format | What it is |
|---|---|---|
| `docs/Architecture-Design-Document.pdf` | PDF (~2.8 MB) | Full ADD — layers, components, runtime flows, cross-cutting concerns, design-decision rationale, with embedded PlantUML diagrams. Generated by `scripts/generate_architecture_pdf.py`. |
| `docs/TokenOptimizer_Documentation.pdf` | PDF | Product/feature documentation. Generated by `scripts/generate_docs_pdf.py`. |
| `docs/FEATURES.md` | Markdown | Feature reference — skills, validation, UI tabs, project layout. |
| `docs/Hackcelerate-Token-Optimisation-Plan.md` | Markdown | The original use-case & development plan (problem, solution, architecture, validation, roadmap, business value). |
| `docs/CHANGELOG.md` | Markdown | Change log (Keep a Changelog format, ISO-8601 dates). |
| `docs/Prompts-Used.md` | Markdown | Reconstructed summary of the prompts used to build the app. |
| `docs/INSTRUCTIONS.md` | Markdown | This document. |

### 6.2 Presentation / pitch deck (`docs/`)

| File | Format | What it is |
|---|---|---|
| `docs/TokenOptimizer-Hackcelerate.pptx` | PowerPoint (13 slides) | Hackcelerate pitch deck — live A/B chart, embedded dashboard, and a demo-video slide. Generated by `scripts/generate_hackcelerate_ppt.py`. |

### 6.3 Demo video (`docs/`)

| File | Format | What it is |
|---|---|---|
| `docs/TokenOptimizer-Demo.mp4` | MP4 (~3.9 MB, 3:14) | Narrated 16-scene voice-over walkthrough of every feature (SAPI TTS + ffmpeg). Generated by `scripts/generate_demo_video.py`. |

### 6.4 Interactive dashboards (project root)

| File | Format | What it is |
|---|---|---|
| `ab_dashboard.html` | Self-contained HTML | A/B validation dashboard — KPI tiles + inline-SVG cost/quality/token charts + data table. Zero dependencies; open in any browser. Regenerate with `tokenopt dashboard`. |

### 6.5 Diagrams (`docs/diagrams/`)

Seven PlantUML workflow diagrams, each available as source (`.puml`), vector (`.svg`),
and raster (`docs/diagrams/png/*.png`):

| Diagram | File stem |
|---|---|
| System overview | `01-system-overview` |
| Document optimize flow | `02-document-optimize` |
| Optimized runner | `03-optimized-runner` |
| Automations | `04-automations` |
| Skills | `05-skills` |
| A/B validation | `06-ab-validation` |
| End-to-end dataflow | `07-end-to-end-dataflow` |

### 6.6 Assets (`docs/assets/`)

| File | What it is |
|---|---|
| `docs/assets/hackcelerate-dashboard.png` | Rendered dashboard screenshot (used in the deck). |
| `docs/assets/video/app_*.png` | UI screenshots used to build the demo video: `app_demo`, `app_github`, `app_jira`, `app_optimized`, `app_optimizer`, `app_skills`. |

### 6.7 Sample inputs (`examples/`)

| File | What it is |
|---|---|
| `examples/jira-issue-sample.txt` | Sample JIRA issue — good input for `compress-prd`. |
| `examples/sample-document.docx` | Sample Word document — good input for `optimize-doc`. |

---

## 7. Regenerating the artefacts

Requires the `docs` extra (`pip install -e ".[docs]"`); the video needs `ffmpeg`
and Windows SAPI, and the diagrams need Java + `plantuml-1.2026.6.jar`.

```bat
.venv\Scripts\python.exe scripts\generate_architecture_pdf.py    REM -> docs\Architecture-Design-Document.pdf
.venv\Scripts\python.exe scripts\generate_docs_pdf.py            REM -> docs\TokenOptimizer_Documentation.pdf
.venv\Scripts\python.exe scripts\generate_hackcelerate_ppt.py    REM -> docs\TokenOptimizer-Hackcelerate.pptx
.venv\Scripts\python.exe scripts\generate_demo_video.py          REM -> docs\TokenOptimizer-Demo.mp4
java -jar plantuml-1.2026.6.jar docs\diagrams\*.puml             REM -> diagram SVG/PNG
tokenopt dashboard                                               REM -> ab_dashboard.html
```

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `run.bat` says venv not found | Run the setup in §2 first. |
| Token counts look approximate | Install the `tokenize` extra for real BPE counts. |
| `--summarize` does nothing | Set `ANTHROPIC_API_KEY` in `.env`, or use the in-UI API-key field. |
| UI window too small / cards clipped | The window sizes to the display work area; maximise or increase display resolution. |
| PDF/PPTX generator import error | Install the `docs` extra: `pip install -e ".[docs]"`. |

---

*Generated 2026-07-15.*
