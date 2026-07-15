# TokenOptimizer — Feature Reference

TokenOptimizer shrinks the text you send to an LLM so you spend fewer tokens
(and less money) per call, while preserving every fact an agent needs. It works
**fully offline with no API key**, and gets even better when a Claude API key or
a local model is available.

---

## 1. Optimization strategies

The pipeline ([`optimize/text_pipeline.py`](src/token_optimizer/optimize/text_pipeline.py))
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
   and a running Ollama server. See [`optimize/local_model.py`](src/token_optimizer/optimize/local_model.py).
3. **Entity-anchored extractive** (`summary_tier: extractive`) — no LLM at all.
   TextRank-style centrality scoring picks the most central sentences, and
   **always keeps** sentences carrying must-keep entities: error/status codes,
   version numbers, issue keys (`ABC-123`), CamelCase identifiers, file paths,
   URLs, and emails — so a summary never silently drops a fact.

Summarization runs **before** line-level compression so it sees clean,
sentence-structured text.

### 1.3 Structured (JIRA/DevOps) optimization (`optimize/pipeline.py`)
For structured items rather than free text: field pre-filtering
([`prefilter.py`](src/token_optimizer/optimize/prefilter.py)) keeps only
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
  ([`integrations/document.py`](src/token_optimizer/integrations/document.py)).
- **JIRA** — fetch issues by JQL.
- **GitHub** — fetch a single PR or all open PRs (optionally with diffs).
- **Jenkins / GitLab / Azure DevOps** — integration clients under
  [`integrations/`](src/token_optimizer/integrations/).

Credentials come from the UI form or fall back to environment / `.env`.

---

## 5. Interfaces

### Packaged skills (`.claude/skills/`)
The two token-optimisation skills are also packaged as invokable Claude Code
skills, each wrapping the CLI commands below:

- **[`prd-compressor`](.claude/skills/prd-compressor/SKILL.md)** — Skill 1: PRD/spec/ticket compression (~67% fewer input tokens).
- **[`codebase-anchor-router`](.claude/skills/codebase-anchor-router/SKILL.md)** — Skill 2: `file:line` anchoring (2a) + complexity-based model routing (2b).

### Desktop UI (`tokenopt ui`)
Tkinter app (no extra deps) with Document / JIRA / GitHub tabs. **Auto-optimizes
on load** so the token review appears immediately. Shows Original vs Optimized
panes and a **Token review** panel: Original / Optimized / Saved (with %) /
Counted-via. Writes `optimized_output.txt` and a per-run log.

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

## 6. Per-run logging (`run_log.py`)

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

## 7. Reliability & safety

- **Graceful degradation** — no API key → offline strategies; no `tiktoken` →
  heuristic; Ollama down → extractive. Nothing hard-fails.
- **Response cache** ([`llm/cache.py`](src/token_optimizer/llm/cache.py)) — repeated
  identical calls are served from disk.
- **No secret logging** — API keys/tokens never appear in logs or output.
- **Offline test suite** — `pytest tests/` covers every strategy with no network
  or API key required.

---

## 8. Configuration (env / `.env`)

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Enables Haiku summarization + exact token counts. |
| `TOKENOPT_MODEL` | `claude-opus-4-8` | Main reasoning model. |
| `TOKENOPT_SUMMARY_MODEL` | `claude-haiku-4-5` | Cheap summarization model. |
| `TOKENOPT_LOCAL_MODEL` | — | Ollama model name for offline abstractive summary. |
| `TOKENOPT_LOCAL_MODEL_URL` | `http://localhost:11434` | Ollama server URL. |
| `TOKENOPT_CACHE_DIR` | `.tokenopt_cache` | Response cache location. |
| `TOKENOPT_LOG_DIR` | `logs` | Per-run log location. |
| `JIRA_*`, `GITHUB_*`, `JENKINS_*`, `GITLAB_*`, `AZDO_*` | — | Integration credentials. |
