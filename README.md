# DevPluseRepo

> **TokenOptimizer** — a token-optimized [Claude](https://www.anthropic.com/) text optimizer.

Point it at a **Word document** (`.docx`) or text file, and it shrinks the text before it ever reaches
the model, writes the optimized text to a file, and reports exactly how many tokens were
saved. A small desktop **UI** lets you pick a document and view the result.

> The same engine also drives automations over **JIRA** and DevOps tools
> (**GitHub, Azure DevOps, GitLab, Jenkins**) — see [Automations](#real-automations) below.

## Document optimizer (default use case)

```powershell
# Desktop UI: select a document, view original vs. optimized text + token savings
tokenopt ui

# Command line: optimize a document, write optimized_output.txt to the current folder
tokenopt optimize-doc --file report.docx
tokenopt optimize-doc --file notes.txt --summarize   # add a Claude Haiku summary pass
```

- **Source**: [`integrations/document.py`](src/token_optimizer/integrations/document.py) reads `.docx` (via `python-docx`), `.txt`, and `.md`.
- **Optimizer**: [`optimize/text_pipeline.py`](src/token_optimizer/optimize/text_pipeline.py) runs prose-aware compression, then optional Haiku summarization.
- **Output**: the optimized text (with a savings header) is written to `optimized_output.txt` in the root/working folder.
- **Tokens**: counted with the API's `count_tokens` when `ANTHROPIC_API_KEY` is set; otherwise a local estimate ([`optimize/tokens.py`](src/token_optimizer/optimize/tokens.py)) so compression works fully offline.
- **UI**: [`ui.py`](src/token_optimizer/ui.py) — a dependency-free Tkinter app.

### Connecting to JIRA and Git in the UI

`tokenopt ui` opens with three source tabs, so you can optimize live data as easily
as a file:

- **Document** — pick a `.docx` / `.txt` / `.md`.
- **JIRA** — enter Base URL, Email, API token and a JQL query, then **Connect & Fetch Issues**.
- **GitHub (Git)** — enter Token, Owner, Repo (and an optional PR number / *Include diff*),
  then **Connect & Fetch**. Leave the PR number blank to pull all open PRs.

Any connection field left blank falls back to your environment / `.env` values
([`.env.example`](.env.example)), so you can either type credentials into the form or
configure them once. Fetching turns the remote data into text
([`integrations/sources.py`](src/token_optimizer/integrations/sources.py)), which then
flows through the same optimize → token-review → `optimized_output.txt` path.

## Why

LLM automations over ticketing/CI systems are expensive because the raw payloads are
huge and mostly boilerplate. TokenOptimizer applies four stacked strategies so you pay
for signal, not noise.

| # | Strategy | Where | What it does |
|---|----------|-------|--------------|
| 1 | **Local pre-filtering** | [`optimize/prefilter.py`](src/token_optimizer/optimize/prefilter.py) | Rule-based field allowlists drop irrelevant JSON before the LLM sees it. 0 tokens, 0 latency. |
| 2 | **Context compression** | [`optimize/compress.py`](src/token_optimizer/optimize/compress.py) | Strip log noise, dedupe repeated lines, head/tail-truncate. Great on CI logs & diffs. |
| 3 | **Smart summarization** | [`optimize/summarize.py`](src/token_optimizer/optimize/summarize.py) | Pre-summarize large inputs with cheap Haiku so Opus reasons over a summary. |
| 4 | **Prompt caching** | [`llm/client.py`](src/token_optimizer/llm/client.py), [`llm/cache.py`](src/token_optimizer/llm/cache.py) | Claude native prompt cache (stable system prefix, ~0.1x reads) + local exact-match cache (0 tokens). |

Every run returns an [`OptimizationResult`](src/token_optimizer/optimize/pipeline.py) with
`raw_tokens`, `optimized_tokens`, `reduction_pct`, and an estimated cost — measured with the
API's `count_tokens` endpoint (never `tiktoken`, which mis-counts Claude tokens).

## Model choices

- Reasoning: **`claude-opus-4-8`** with adaptive thinking (`thinking: {type: "adaptive"}`) and configurable effort.
- Summarization: **`claude-haiku-4-5`** at `low` effort — cheap and fast.

Both are overridable via `TOKENOPT_MODEL` / `TOKENOPT_SUMMARY_MODEL`.

## Install

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env   # then fill in your credentials
```

## Quick start

Run the optimizer on canned data — no external credentials needed, only `ANTHROPIC_API_KEY`:

```powershell
tokenopt demo
```

### Real automations

```powershell
tokenopt triage-jira --jql "project = ABC AND status = 'To Do'"
tokenopt triage-jenkins --job my-pipeline --build lastBuild

# GitHub: review one PR (optionally post the review back as a comment)
tokenopt review-github-pr --owner octocat --repo hello --number 42
tokenopt review-github-pr --owner octocat --repo hello --number 42 --post-comment

# GitHub: triage every open PR in a repo in a single optimized call
tokenopt triage-github-prs --owner octocat --repo hello
tokenopt triage-github-prs --owner octocat --repo hello --diffs   # deeper read
```

The PR reviewer compresses the unified diff with a **diff-aware** pass
([`compress_diff`](src/token_optimizer/optimize/compress.py)) that keeps hunk headers
and `+/-` lines while collapsing unchanged context — typically the largest single
token saving on a code-review prompt.

## Library usage

```python
from token_optimizer import Config, OptimizedRunner

runner = OptimizedRunner(Config())
result = runner.run(
    system="You are a triage assistant...",   # stable, cached prefix
    task="Triage these issues.",
    items=jira_issues,                          # raw dicts from a connector
    profile="jira_issue",
)
print(result.answer)
print(result.summary())   # raw vs optimized tokens, cache hits, cost
```

## Layout

```
src/token_optimizer/
  config.py              env-driven configuration
  llm/                   Claude client (caching, count_tokens, adaptive thinking)
  optimize/              the 4 strategies + pipeline that composes them
  integrations/          JIRA, GitHub, Azure DevOps, GitLab, Jenkins connectors
  automations/           ready-made flows (JIRA triage, Jenkins RCA)
  cli.py                 `tokenopt` command
tests/                   offline tests for the deterministic strategies
```

## Tests

```powershell
pip install pytest
pytest tests/ -v
```

The tests cover pre-filtering, compression, and caching — all offline, no API key required.

## Additional docs

- [Token-Optimizer.md](Token-Optimizer.md) — supplementary notes.
