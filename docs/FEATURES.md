# TokenOptimizer — Feature Reference

TokenOptimizer shrinks the text you send to an LLM so you spend fewer tokens
(and less money) per call, while preserving every fact an agent needs. It works
**fully offline with no API key**, and gets even better when a Claude API key or
a local model is available.

On top of the general optimizer, it ships **two feature-development skills** that
cut token spend during AI-assisted feature work — PRD compression and codebase
anchoring + model routing — validated by an offline A/B suite and a dashboard.

> Source links below are relative to this file (`docs/`), so they point up one
> level into [`../src/token_optimizer/`](../src/token_optimizer/).

---

## 1. Optimization strategies

The pipeline ([`optimize/text_pipeline.py`](../src/token_optimizer/optimize/text_pipeline.py))
runs these in order. Every stage is **skipped-if-noop** and only recorded when it
actually changes the text, so the reported `stages` list reflects what really fired.

### 1.1 Deterministic offline reductions (`optimize/local.py`) — no API, no model
Always run; these are what make the offline path actually reduce clean prose.

| Stage | What it does |
|---|---|
| `unicode` | Folds fancy Unicode to ASCII (smart quotes, em/en dashes, ellipsis, NBSP, ligatures), strips zero-width chars and emoji — all of which cost extra BPE tokens. |
| `framing` | Removes conversational / LLM packaging: preambles ("Sure! Here's…"), sign-offs ("Hope this helps"), and follow-up offers ("Would you like me to…?"). |
| `boilerplate` | Drops page numbers, "Page X of Y", "Confidential", copyright lines, horizontal rules, and table-of-contents dot leaders. |
| `fields` | **Structure-aware**: collapses `Label:` / value-on-next-lines blocks (Jira tickets, bug reports) into tight `label: value` lines, and drops fields whose only value is a placeholder like `[Leave blank…]`. |
| `punctuation` | Collapses decorative/repeated punctuation (`!!!`→`!`, `.....`→`...`) and bullet glyphs. |
| `filler` | Substitutes verbose phrases with concise equivalents (`in order to`→`to`, `due to the fact that`→`because`) and deletes empty filler ("it should be noted that"). |
| `dedupe-paragraphs` | Removes near-duplicate paragraphs (normalized fingerprint, punctuation/case-insensitive). |
| `compress` | Final pass: collapses whitespace, dedupes repeated lines (annotated `(xN)`), and head/tail-truncates anything past the char cap. |

### 1.2 Summarization tiers (optional, `--summarize` / UI checkbox)
Chosen automatically, **best available first**:

1. **Claude Haiku** (`summary_tier: haiku`) — abstractive rewrite into dense,
   agent-ready prose. Requires `ANTHROPIC_API_KEY`. Highest quality.
2. **Local Ollama model** (`summary_tier: local-model`) — abstractive, runs
   entirely on your machine, **zero cloud tokens**. Requires `TOKENOPT_LOCAL_MODEL`
   and a running Ollama server. See [`optimize/local_model.py`](../src/token_optimizer/optimize/local_model.py).
3. **Entity-anchored extractive** (`summary_tier: extractive`) — no LLM at all.
   TextRank-style centrality scoring picks the most central sentences, and
   **always keeps** sentences carrying must-keep entities: error/status codes,
   version numbers, issue keys (`ABC-123`), CamelCase identifiers, file paths,
   URLs, and emails — so a summary never silently drops a fact.

Summarization runs **before** line-level compression so it sees clean,
sentence-structured text.

### 1.3 Structured (JIRA/DevOps) optimization (`optimize/pipeline.py`)
For structured items rather than free text: field pre-filtering
([`prefilter.py`](../src/token_optimizer/optimize/prefilter.py)) keeps only
task-relevant fields, then compression, then optional summarization, before a
single cached Claude call. Reports raw-vs-optimized tokens and estimated cost.

### 1.4 Diff-aware compression (`optimize/compress.py::compress_diff`)
Keeps file/hunk headers and changed (`+`/`-`) lines, collapses unchanged context
— for token-cheap PR review.

---

## 2. Token counting

`optimize/tokens.py` counts tokens with the best backend available:

1. **API `count_tokens`** when an API key is set (exact for Claude).
2. **`tiktoken`** (`cl100k_base`) offline — a real BPE tokenizer (install with
   `pip install tiktoken` or `pip install -e .[tokenize]`).
3. **Char/word heuristic** as a last resort.

The chosen backend is reported per run as `token_method` (`api` / `tiktoken` /
`estimate`).

---

## 3. Minimal prompt request

`text_pipeline.build_prompt_request()` assembles the smallest reasonable
Messages-API request: a cached `system` prefix kept separate (so prompt caching
stays hot) + a terse task line + the optimized data under one compact `<data>`
delimiter — no repeated instructions, no pretty-print padding.

---

## 4. Input sources

- **Documents** — `.docx` (via `python-docx`), `.txt`, `.md`, `.log`
  ([`integrations/document.py`](../src/token_optimizer/integrations/document.py)).
- **JIRA** — fetch issues by JQL.
- **GitHub** — fetch a single PR or all open PRs (optionally with diffs).
- **Jenkins / GitLab / Azure DevOps** — integration clients under
  [`integrations/`](../src/token_optimizer/integrations/).

Credentials come from the UI form or fall back to environment / `.env`.

---

## 5. Feature-development skills

Two skills ([`skills/`](../src/token_optimizer/skills/)) that optimise AI token
usage during feature development. All three components are deterministic and run
fully offline.

### 5.1 Skill 1 — PRD compression (`skills/prd/compressor.py`)
Distills a verbose PRD / spec / ticket into a dense, structured set of
**requirement atoms** before it reaches the LLM.

- Normalises unicode, strips boilerplate, then segments into units (bullets kept
  whole; prose split into sentences).
- Classifies each unit into a requirement **category** — `goal`,
  `acceptance-criteria`, `constraint`, `non-functional`, `dependency`,
  `out-of-scope` — and **drops low-signal framing** (exec summaries, background,
  hedging) that carries no decision.
- **Acceptance criteria are preserved verbatim** (only whitespace-normalised) so
  the build is never checked against a paraphrase; everything else is de-hedged
  and de-duplicated.
- Re-renders as terse bullets grouped by category.

`compress_prd(text)` returns a `PRDCompressionResult` (raw/compressed tokens,
`reduction_pct`, atoms, dropped-unit count). **~67–73% input-token reduction** on
the validation dataset — a floor of 67% is locked by tests.

### 5.2 Skill 2a — Codebase anchoring (`skills/anchor/`)
Grounds an AI plan in the real repository so steps reference verifiable code.

- [`indexer.py`](../src/token_optimizer/skills/anchor/indexer.py) walks a repo and
  builds a symbol table with exact `file:line` locations — **AST-based for
  Python** (accurate), regex fallback for JS/TS/JSX/TSX, Java, Go, Ruby, and C#.
- [`anchor.py`](../src/token_optimizer/skills/anchor/anchor.py) resolves each plan
  step's symbol-like mentions to a real `path:line` **anchor**; symbol-like terms
  that resolve to nothing are recorded as `unresolved_terms` and **flagged as
  possible hallucinations** rather than silently accepted.
- `anchoring_accuracy(anchors)` reports the fraction of steps that resolved.

### 5.3 Skill 2b — Model routing (`skills/router/`)
Routes each task to the cheapest capable model.

- [`classifier.py`](../src/token_optimizer/skills/router/classifier.py) scores a
  task as **trivial / standard / complex** from keyword + structural signals and
  returns a `confidence`.
- [`router.py`](../src/token_optimizer/skills/router/router.py) maps the tier to a
  model — `claude-haiku-4-5` (trivial) → `claude-sonnet-5` (standard) →
  `claude-opus-4-8` (complex) — and applies a **confidence-threshold fallback**:
  below the threshold it upgrades one tier toward premium, so a cheap model is
  never chosen on a coin-flip (a wrong answer costs more in regeneration than the
  routing saved).

---

## 6. A/B validation & dashboard

The [`evaluation/`](../src/token_optimizer/evaluation/) package proves the
cost/quality claims with a deterministic, offline harness.

- **Dataset** ([`datasets.py`](../src/token_optimizer/evaluation/datasets.py)) — 8
  deliberately verbose feature-request PRDs across **2 business units** (Payments,
  Platform), each wrapping a small requirement core in realistic framing.
- **A/B harness** ([`ab_runner.py`](../src/token_optimizer/evaluation/ab_runner.py))
  — for each case, compares **baseline** (raw PRD → premium model, no anchoring)
  vs **optimised** (compressed PRD → anchored plan → routed model) and aggregates
  cost, input-token reduction, tokens saved, and quality.
- **25-point quality rubric** ([`quality_rubric.py`](../src/token_optimizer/evaluation/quality_rubric.py))
  — correctness, completeness, anchoring, actionability, no-hallucination (0–5
  each), scored deterministically so runs are reproducible.
- **Cost model** ([`cost.py`](../src/token_optimizer/evaluation/cost.py)) — tokens
  × per-model list price, mirroring the live client's pricing.
- **Dashboard** ([`dashboard.py`](../src/token_optimizer/evaluation/dashboard.py))
  — `build_dashboard()` renders a **self-contained HTML file** (inline SVG, no
  libraries, no network): KPI tiles + cost/quality/tokens-saved bar charts + a
  full data table.

**Validated outcome (test-locked):** ~73% average PRD compression, ~58% average
cost savings, **24.0/25** average optimised quality (baseline 19.5) across the
8 cases / 2 BUs. See `test_prd_compression_meets_67_percent_claim` and
`test_ab_suite_meets_savings_and_quality_targets` in
[`tests/test_hackcelerate.py`](../tests/test_hackcelerate.py).

---

## 7. Interfaces

### Packaged skills (`.claude/skills/`)
The skills are also packaged as invokable Claude Code skills, each wrapping the
CLI commands below:

- **[`prd-compressor`](../.claude/skills/prd-compressor/SKILL.md)** — Skill 1: PRD/spec/ticket compression.
- **[`codebase-anchor-router`](../.claude/skills/codebase-anchor-router/SKILL.md)** — Skill 2: `file:line` anchoring (2a) + complexity-based model routing (2b).

### Desktop UI (`tokenopt ui`)
Dependency-free Tkinter app ([`ui/app.py`](../src/token_optimizer/ui/app.py)) with
**three top-level tabs**:

1. **Token Optimizer** — Document / JIRA / GitHub source tabs; **auto-optimizes on
   load**; Original vs Optimized panes and a Token-review panel (Original /
   Optimized / Saved % / Counted-via). Writes `optimized_output.txt` + a per-run log.
   The **Document** source has an optional **Anthropic API key** field: enter a key
   to opt into Claude (Haiku) summarization and exact API token counts for a more
   effective result (the mode chip and summarize label update live). Blank keeps it
   fully offline; a key in your `.env` is used automatically.
2. **Feature-Dev Skills** — a 2-column card grid (Skill 1 PRD compression, Skill 2b
   router, Skill 2a anchoring, A/B validation) on the left half and a shared result
   console on the right half.
3. **Dashboard** — KPI tiles + **native bar charts** (cost & quality per case,
   drawn on a Tk canvas) with **Run A/B & Refresh** and **Open HTML Dashboard**;
   auto-runs the suite the first time the tab is opened.

Ctrl+Tab / Ctrl+Shift+Tab switch tabs; the window sizes itself to the display's
work area. `TOKENOPT_UI_TAB=skills|dashboard` opens straight to a tab (demos/tests).

**Guided Demo** (Help → Guided Demo) — an automated, video-style walkthrough: a
narration caption box auto-advances through 12 scenes, switching tabs and running
each feature live (compress a sample PRD, route a task, anchor a plan, refresh the
dashboard), with Prev / Pause / Next / Close controls and a progress bar.
`TOKENOPT_UI_DEMO=1` auto-starts it on launch.

### Command line (`tokenopt …`)
| Command | Purpose |
|---|---|
| `optimize-doc --file F [--summarize] [--out O]` | Optimize a document. |
| `compress-prd --file F [--out O]` | **Skill 1** — compress a verbose PRD into dense requirement atoms (~67% fewer input tokens). |
| `anchor-plan --plan F [--repo R]` | **Skill 2a** — anchor each plan step (one per line) to real `file:line` references; flags unresolved (hallucinated) symbols. |
| `route --task "…"` | **Skill 2b** — classify a task's complexity and route it to the cheapest capable model. |
| `ab-suite [--repo R]` | **Eval** — run the 8-case, 2-BU A/B suite (baseline vs optimised) and print cost/token/quality deltas. |
| `dashboard [--repo R] [--out O]` | **Eval** — render the A/B results to a self-contained HTML dashboard (inline-SVG charts, no deps). |
| `ui` | Launch the desktop UI. |
| `triage-jira --jql Q [--max N]` | Triage JIRA issues. |
| `triage-jenkins --job J [--build B]` | Root-cause a Jenkins failure. |
| `review-github-pr --owner O --repo R --number N [--post-comment]` | Review a PR. |
| `triage-github-prs --owner O --repo R [--diffs]` | Triage all open PRs. |
| `demo` | Run on canned data. |

### Windows launcher
`run.bat` — double-click to open the UI, or `run.bat <command> …` from a
terminal. Uses the project venv directly; no activation needed.

---

## 8. Per-run logging (`core/run_log.py`)

**Every run writes one timestamped log file** under `logs/` (configurable via
`TOKENOPT_LOG_DIR`). Each file has a human-readable report **and** a
machine-parseable `--- JSON ---` block, capturing:

- Run ID, timestamp, command, and status (`ok` / `error`)
- Source (file path / JQL / PR) and resolved options
- Config snapshot — **secrets reduced to booleans** (`api_key_configured: true`),
  never their values
- Metrics: raw/optimized tokens, tokens saved, reduction %, `token_method`,
  `summary_tier`, stages fired, char counts, estimated cost, `duration_ms`
- Environment: app version, Python version, platform
- Output path, and any error message

Logs are `.gitignore`d. Logging never raises — a logging failure can't break a run.

---

## 9. Reliability & safety

- **Graceful degradation** — no API key → offline strategies; no `tiktoken` →
  heuristic; Ollama down → extractive. Nothing hard-fails.
- **Response cache** ([`core/llm/cache.py`](../src/token_optimizer/core/llm/cache.py)) — repeated
  identical calls are served from disk.
- **No secret logging** — API keys/tokens never appear in logs or output.
- **Offline test suite** — `pytest tests/` (58 tests) covers every strategy and
  both skills with no network or API key required.

---

## 10. Project layout

Layered `src/` package: cross-cutting infrastructure in `core/`, the product
skills in `skills/`, and everything else grouped by responsibility.

```
src/token_optimizer/
  cli.py                 `tokenopt` command (all subcommands)
  core/                  cross-cutting infrastructure
    config.py            env-driven configuration
    run_log.py           per-run logging
    llm/                 Claude client + response cache
  skills/                feature-development skills
    prd/                 Skill 1  — PRD compression
    anchor/              Skill 2a — codebase file:line anchoring
    router/              Skill 2b — complexity-based model routing
  optimize/              optimization pipeline (local reductions, compress,
                         summarize, prefilter, tokens, text/structured pipelines)
  integrations/          JIRA, GitHub, Azure DevOps, GitLab, Jenkins, documents
  automations/           ready-made flows (JIRA triage, Jenkins RCA, PR review)
  evaluation/            A/B runner, 25-pt rubric, cost model, dataset, dashboard
  ui/                    desktop Tkinter app (app.py, `python -m token_optimizer.ui`)
docs/                    FEATURES.md, plan, generated documentation PDF
examples/                sample PRD / document inputs
tests/                   offline test suites (test_optimize, test_hackcelerate)
```

---

## 11. Configuration (env / `.env`)

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Enables Haiku summarization + exact token counts. |
| `TOKENOPT_MODEL` | `claude-opus-4-8` | Main reasoning model. |
| `TOKENOPT_SUMMARY_MODEL` | `claude-haiku-4-5` | Cheap summarization model. |
| `TOKENOPT_LOCAL_MODEL` | — | Ollama model name for offline abstractive summary. |
| `TOKENOPT_LOCAL_MODEL_URL` | `http://localhost:11434` | Ollama server URL. |
| `TOKENOPT_CACHE_DIR` | `.tokenopt_cache` | Response cache location. |
| `TOKENOPT_LOG_DIR` | `logs` | Per-run log location. |
| `TOKENOPT_UI_TAB` | — | Open the UI straight to `skills` or `dashboard` (demos/tests). |
| `TOKENOPT_UI_DEMO` | — | Set to `1` to auto-start the guided demo on UI launch. |
| `JIRA_*`, `GITHUB_*`, `JENKINS_*`, `GITLAB_*`, `AZDO_*` | — | Integration credentials. |
