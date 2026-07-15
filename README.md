# DevPluseRepo

> **TokenOptimizer** — a token-optimized [Claude](https://www.anthropic.com/) text optimizer.

Point it at a **Word document** (`.docx`) or text file, and it shrinks the text before it ever reaches
the model, writes the optimized text to a file, and reports exactly how many tokens were
saved. A small desktop **UI** lets you pick a document and view the result.

> The same engine also drives automations over **JIRA** and DevOps tools
> (**GitHub, Azure DevOps, GitLab, Jenkins**) — see [Automations](#real-automations) below.

> 📖 **Full feature reference:** [FEATURES.md](docs/FEATURES.md) — every optimization
> strategy, summary tier, token-counting backend, interface, and the per-run logging.
> Every run writes a detailed log to `logs/`.
>
> 🏛️ **Architecture:** [Architectural Design Document (PDF)](docs/Architecture-Design-Document.pdf)
> — layers, components, runtime flows, and design decisions
> (regenerate with `python scripts/generate_architecture_pdf.py`).
>
> 📊 **Pitch:** [Hackcelerate deck (PPTX)](docs/TokenOptimizer-Hackcelerate.pptx)
> — 12 slides with a live A/B chart (regenerate with
> `python scripts/generate_hackcelerate_ppt.py`).

## Document optimizer (default use case)

```powershell
# Desktop UI: select a document, view original vs. optimized text + token savings
tokenopt ui

# Command line: optimize a document, write optimized_output.txt to the current folder
tokenopt optimize-doc --file report.docx
tokenopt optimize-doc --file notes.txt --summarize   # add a summary pass (Haiku, or offline extractive with no key)
```

- **Source**: [`integrations/document.py`](src/token_optimizer/integrations/document.py) reads `.docx` (via `python-docx`), `.txt`, and `.md`.
- **Optimizer**: [`optimize/text_pipeline.py`](src/token_optimizer/optimize/text_pipeline.py) runs, all offline: deterministic reductions ([`optimize/local.py`](src/token_optimizer/optimize/local.py) — Unicode→ASCII, conversational/LLM-framing removal, boilerplate/page-number stripping, structure-aware field collapsing, decorative-punctuation and filler-phrase collapse, paragraph dedup), then whitespace/dedupe compression, then an optional summary pass.
- **Summary tiers** (`--summarize`), chosen best-first by what's available: **Claude Haiku** (API key) → a **local Ollama model** (`TOKENOPT_LOCAL_MODEL`, abstractive, *no cloud tokens*) → a **no-LLM entity-anchored extractive** summarizer that never drops error codes, versions, IDs, paths, or labels. So the big win works fully offline, and matches API quality when a local model is available.
- **Minimal request**: `build_prompt_request()` assembles the smallest reasonable Messages-API request — cached system prefix + terse task + optimized data under one compact delimiter.
- **Output**: the optimized text (with a savings header) is written to `optimized_output.txt` in the root/working folder.
- **Tokens**: counted with the API's `count_tokens` when `ANTHROPIC_API_KEY` is set; otherwise offline via `tiktoken` (real BPE), falling back to a char/word estimate if `tiktoken` isn't installed ([`optimize/tokens.py`](src/token_optimizer/optimize/tokens.py)). The whole pipeline works fully offline.
- **UI**: [`ui/app.py`](src/token_optimizer/ui/app.py) — a dependency-free Tkinter app with three top-level tabs: **Token Optimizer** (document/JIRA/GitHub), **Feature-Dev Skills** (the two skills + A/B validation), and **Dashboard** (native cost/quality charts).

### Connecting to JIRA and Git in the UI

The **Token Optimizer** tab opens with three source sub-tabs, so you can optimize
live data as easily as a file:

- **Document** — pick a `.docx` / `.txt` / `.md`. Optionally paste an **Anthropic API key**
  to opt into Claude (Haiku) summarization + exact token counts for a more effective
  result; blank stays fully offline (a key in `.env` is used automatically).
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
| 4 | **Prompt caching** | [`core/llm/client.py`](src/token_optimizer/core/llm/client.py), [`core/llm/cache.py`](src/token_optimizer/core/llm/cache.py) | Claude native prompt cache (stable system prefix, ~0.1x reads) + local exact-match cache (0 tokens). |

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

## Feature-development skills & A/B validation

Two skills that optimise AI token usage during feature development, plus an
offline A/B suite that proves the cost/quality outcome. Full detail in
[docs/FEATURES.md §5–6](docs/FEATURES.md).

```powershell
# Skill 1 — compress a verbose PRD into dense requirement atoms (~67% smaller)
tokenopt compress-prd --file prd.docx

# Skill 2a — anchor plan steps (one per line) to real file:line refs; flags hallucinations
tokenopt anchor-plan --plan plan.txt --repo src

# Skill 2b — classify a task and route it to the cheapest capable model
tokenopt route --task "rename a variable and fix a typo"      # -> haiku
tokenopt route --task "redesign auth for concurrency"          # -> opus

# Validation — 8-case / 2-BU baseline-vs-optimised comparison, and an HTML dashboard
tokenopt ab-suite --repo src
tokenopt dashboard --repo src        # writes/opens ab_dashboard.html
```

- **Skill 1 — PRD compression** ([`skills/prd/compressor.py`](src/token_optimizer/skills/prd/compressor.py)): extracts decision-relevant requirement atoms, keeps acceptance criteria verbatim.
- **Skill 2a — Codebase anchoring** ([`skills/anchor/`](src/token_optimizer/skills/anchor/)): AST/regex symbol index → `file:line` anchors, flags unresolved (hallucinated) references.
- **Skill 2b — Model routing** ([`skills/router/`](src/token_optimizer/skills/router/)): complexity classifier + confidence-threshold fallback to premium.
- **Validation** ([`evaluation/`](src/token_optimizer/evaluation/)): **~73% compression, ~58% cost savings, 24.0/25 quality** across 8 cases / 2 BUs — locked by tests.

The skills are also packaged as invokable Claude Code skills under
[`.claude/skills/`](.claude/skills/).

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

Layered `src/` package — cross-cutting infrastructure in `core/`, the product
skills in `skills/`, everything else grouped by responsibility.

```
src/token_optimizer/
  cli.py                 `tokenopt` command (all subcommands)
  core/                  config, per-run logging, Claude client + cache
  skills/                prd/ (Skill 1), anchor/ (Skill 2a), router/ (Skill 2b)
  optimize/              the strategies + pipelines that compose them
  integrations/          JIRA, GitHub, Azure DevOps, GitLab, Jenkins, documents
  automations/           ready-made flows (JIRA triage, Jenkins RCA, PR review)
  evaluation/            A/B runner, 25-pt rubric, cost model, dataset, dashboard
  ui/                    desktop Tkinter app (app.py)
docs/                    FEATURES.md, plan, documentation PDF
examples/                sample PRD / document inputs
tests/                   offline test suites (deterministic, no API key)
```

See [docs/FEATURES.md §10](docs/FEATURES.md) for the annotated tree and
[docs/CHANGELOG.md](docs/CHANGELOG.md) for the full change history.

## Tests

```powershell
pip install pytest
pytest tests/ -v
```

The tests cover pre-filtering, compression, and caching — all offline, no API key required.

---

# Appendix: Token Optimizer — Techniques to Reduce Token Usage & AI Credits

**Version:** 1.0
**Last updated:** 2026-07-08
**Audience:** Engineers and architects building applications on top of Large Language Models (LLMs)

> This appendix inlines the reference guide previously kept in `Token-Optimizer.md`.

## 1. Introduction

Every interaction with an LLM is billed by **tokens**, not by requests. A token is a
sub-word unit produced by the model's tokenizer (roughly ~4 characters or ~0.75 words
of English text). Both what you send (**input / prompt tokens**) and what the model
returns (**output / completion tokens**) are metered, and output tokens are almost
always priced higher than input tokens (commonly 3x–5x).

Because cost scales linearly with tokens and roughly quadratically with context length
in terms of latency, **token optimization** is simultaneously a cost lever, a latency
lever, and a quality lever (a smaller, cleaner context usually produces better answers).

This document catalogs the practical techniques a "token optimizer" layer can apply,
organized from highest-leverage/lowest-effort to more advanced architectural patterns.

### 1.1 The cost model in one formula

```
cost_per_call = (input_tokens  × price_in)
              + (output_tokens × price_out)
              + (cache_write_tokens × price_cache_write)   # if using prompt caching
              - (cache_read_tokens × price_in × discount)  # cache reads are cheaper

total_cost   = Σ cost_per_call  over all calls (including retries & agent loops)
```

Key implications:
- **Output tokens dominate.** Reducing verbosity of responses often beats trimming prompts.
- **Repeated calls multiply everything.** Agent loops and retries can 10x a naive estimate.
- **Caching changes the math.** Static context can be re-billed at a fraction of the price.

## 2. Quick reference: technique catalog

| # | Technique | Primarily reduces | Effort | Typical saving |
|---|-----------|-------------------|--------|----------------|
| 1 | Prompt compression & pruning | Input | Low | 10–40% |
| 2 | Output control (max_tokens, format) | Output | Low | 20–60% |
| 3 | Prompt caching | Input | Low–Med | 50–90% on cached portion |
| 4 | Model routing / tiering | Both | Med | 40–80% |
| 5 | Context window management / truncation | Input | Med | 30–70% |
| 6 | Retrieval-Augmented Generation (RAG) | Input | Med–High | 50–95% |
| 7 | Summarization & memory compaction | Input | Med | 40–80% |
| 8 | Semantic response caching | Both | Med | Up to 100% on hits |
| 9 | Batching & request consolidation | Both | Low–Med | 20–50% |
| 10 | Few-shot example minimization | Input | Low | 10–30% |
| 11 | Structured output / function calling | Output | Low | 20–50% |
| 12 | Streaming + early termination | Output | Low | Variable |
| 13 | Token-aware chunking | Input | Med | Variable |
| 14 | Fine-tuning / distillation | Input | High | 50–90% on prompts |
| 15 | Speculative & cascaded inference | Both | High | 30–60% |

## 3. Techniques in detail

### 3.1 Prompt compression & pruning

**Idea:** Remove tokens that don't change the model's output.

Techniques:
- **Whitespace & formatting normalization** — collapse repeated spaces/newlines, strip
  markdown decoration the model doesn't need. Minor but free.
- **Remove redundant instructions** — say each rule once. Duplicated "be concise" lines
  waste tokens on every call.
- **Abbreviation & symbol substitution** — replace verbose boilerplate with compact
  equivalents where meaning is preserved.
- **Lossy semantic compression (e.g., LLMLingua)** — a small model scores each token's
  importance and drops low-information tokens, achieving 2x–20x prompt compression with
  minimal quality loss. Useful for long contexts / RAG passages.
- **Strip dead context** — remove stack traces, HTML boilerplate, base64 blobs, license
  headers, and other high-token/low-signal content before sending.

**Technical note:** Always measure with a real tokenizer (e.g., `tiktoken` for OpenAI,
the provider's token-counting endpoint for others) — character-count heuristics mislead,
especially for code, JSON, and non-English text where tokens/char ratios differ sharply.

```python
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")
def count(text): return len(enc.encode(text))
```

### 3.2 Output control

Output tokens are the most expensive. Control them explicitly:

- **`max_tokens` / `max_output_tokens`** — hard cap. Set it to the smallest value that
  fits the task; don't leave it at the model maximum.
- **Ask for terse output** — "Answer in one sentence", "Return only the JSON", "No
  preamble". Prompt phrasing measurably shortens completions.
- **Forbid restating the question** — models often echo the prompt; instruct against it.
- **Stop sequences** — define delimiters so generation halts as soon as the answer is
  complete instead of rambling.
- **Constrain the schema** — a fixed enum or numeric answer is a handful of tokens vs. a
  paragraph.

### 3.3 Prompt caching

Most major providers now support **prompt caching**: a static prefix of the prompt (system
prompt, tool definitions, large documents, few-shot examples) is cached server-side, and
subsequent calls that reuse that exact prefix are billed at a large discount (often 90%
cheaper reads) and run faster.

Best practices:
- **Put stable content first, volatile content last.** Caching works on prefixes — order
  matters. System prompt + tools + docs (stable) → then the user's turn (volatile).
- **Keep the prefix byte-identical.** Any change (even a timestamp) invalidates the cache.
- **Mind the TTL.** Caches expire (commonly ~5 minutes of inactivity); high-traffic
  endpoints benefit most.
- **Cache-write costs a premium** (~25% more than normal input), so caching pays off only
  when the prefix is reused enough times to amortize the write.

This is the single highest-leverage optimization for chatbots and agents with large,
reused system prompts.

### 3.4 Model routing / tiering

Not every request needs the flagship model. Route by difficulty:

- **Tiered models** — send trivial/classification tasks to a small, cheap model; escalate
  only hard reasoning tasks to the large model. A cheap model can cost 1/10th–1/30th.
- **Router/classifier** — a lightweight classifier (rules, embeddings, or a tiny LLM)
  decides which model handles each request.
- **Confidence-based escalation (cascade)** — try the cheap model first; if its confidence
  (self-reported or via a verifier) is low, retry on the big model. Only the hard fraction
  incurs premium cost.

```
request → classifier ──easy──► small model
                     └─hard──► large model
```

### 3.5 Context window management

For multi-turn conversations, the full history is resent every turn — token cost grows
quadratically over a session if left unmanaged. Strategies:

- **Sliding window** — keep only the last N turns verbatim.
- **Token-budgeted truncation** — drop oldest messages until the history fits a budget.
- **Priority pinning** — always keep the system prompt and the most recent user turn;
  evict middle history first.
- **Relevance filtering** — keep only turns semantically relevant to the current query
  (via embeddings), drop the rest.

### 3.6 Retrieval-Augmented Generation (RAG)

Instead of stuffing an entire knowledge base into every prompt, **retrieve only the
relevant chunks**:

1. Chunk documents (token-aware; see 3.13) and embed them into a vector store.
2. At query time, embed the query and retrieve top-k most similar chunks.
3. Inject only those k chunks into the prompt.

This replaces a 100k-token document dump with, say, 2k tokens of relevant passages — often
a 50–95% input reduction *and* better answers (less distraction). Tune `k` and chunk size
to the minimum that preserves accuracy. Add a **re-ranker** to keep `k` small without
losing recall.

### 3.7 Summarization & memory compaction

For long agent runs or chats, periodically **replace verbose history with a summary**:

- **Rolling summarization** — when history exceeds a threshold, summarize the oldest
  portion into a compact synopsis and keep recent turns verbatim.
- **Hierarchical memory** — short-term (raw recent turns) + long-term (summarized facts) +
  entity/fact store (structured key-value).
- **Compaction** — collapse tool outputs and intermediate reasoning into their conclusions
  once no longer needed.

Trade-off: summarization itself costs tokens (one extra call), so trigger it on a budget
threshold, not every turn.

### 3.8 Semantic response caching

Cache *answers*, not just prompts. When a new query is semantically similar to a previously
answered one (cosine similarity of embeddings above a threshold), return the stored answer
and skip the LLM call entirely (up to 100% saving on hits).

- Use an embedding index (e.g., GPTCache pattern) keyed by query embedding.
- Set a similarity threshold carefully — too loose returns wrong answers, too tight lowers
  the hit rate.
- Add TTLs and invalidation for time-sensitive data.
- Best for FAQ-like, high-repetition traffic; poor for highly personalized/unique queries.

### 3.9 Batching & request consolidation

- **Batch API** — many providers offer an asynchronous batch endpoint at ~50% discount for
  non-latency-sensitive workloads (bulk classification, enrichment, evals).
- **Consolidate calls** — if you make N independent small calls that share the same large
  context, combine them into one call that returns N answers, so the shared context is
  billed once instead of N times.
- **Avoid chatty agent loops** — each agent step re-sends the growing context; fewer, more
  capable steps beat many tiny ones.

### 3.10 Few-shot example minimization

Few-shot examples are pure input cost paid on every call.

- Use the **minimum number of examples** that achieves the accuracy target — test 0/1/3/5.
- Prefer **shorter, representative** examples over long ones.
- **Cache** the example block (3.3) so it's cheap after the first call.
- Consider replacing few-shot with **fine-tuning** (3.14) when volume is high.

### 3.11 Structured output / function calling

Asking for JSON/structured output via a schema (function calling, tool use, or a
JSON-mode/grammar constraint) makes completions **compact and deterministic**: no prose
wrapper, no "Sure, here's...", just the data. This cuts output tokens and eliminates
fragile parsing/retries (retries are pure wasted cost).

### 3.12 Streaming + early termination

Stream the response and **stop as soon as you have what you need** (e.g., the first valid
JSON object, or enough of a list). You still pay for generated tokens, but early
termination prevents paying for a long tail you'll discard. Also improves perceived
latency.

### 3.13 Token-aware chunking

When splitting documents for RAG or processing:
- Chunk by **token count**, not character count, to pack context windows precisely.
- Use **semantic boundaries** (paragraphs, sections) with small overlaps so chunks stay
  coherent and you don't need redundant large overlaps.
- Right-sized chunks improve retrieval precision → smaller `k` → fewer tokens.

### 3.14 Fine-tuning & distillation

If a long prompt (detailed instructions + many few-shot examples) is used at high volume,
**fine-tune** a smaller model to internalize that behavior. The runtime prompt shrinks to
just the input, eliminating thousands of instruction/example tokens per call.
**Distillation** (train a small model on a large model's outputs) similarly moves cost from
per-call tokens to a one-time training cost. High upfront effort; large sustained savings.

### 3.15 Speculative & cascaded inference

- **Cascades** (see 3.4) — cheap-first, escalate-on-low-confidence.
- **Speculative decoding** — a small draft model proposes tokens the large model verifies;
  reduces latency/compute (mostly a provider-side or self-hosted concern).
- **Self-consistency budgeting** — techniques like sampling multiple reasoning paths are
  accurate but multiply cost; cap the number of samples and only use on hard queries.

## 4. Reference architecture for a Token Optimizer layer

Place an optimizer between your application and the LLM provider:

```
                ┌──────────────────────── Token Optimizer ─────────────────────────┐
 App request ──►│ 1. Semantic cache lookup ──hit──────────────────────────► return │
                │        │ miss                                                     │
                │ 2. Prompt build: RAG retrieve → compress → dedupe               │
                │ 3. Context manager: window/truncate/summarize history          │
                │ 4. Model router: classify difficulty → pick model tier          │
                │ 5. Attach prompt cache markers (stable prefix first)            │
                │ 6. Set max_tokens, stop sequences, structured schema           │
                │ 7. Call provider (batch if async-tolerable) with streaming     │
                │ 8. Early-terminate; store answer in semantic cache             │
                │ 9. Meter tokens & cost; log for feedback loop                  │
                └────────────────────────────────────────────────────────────────┘
```

### 4.1 Minimal implementation sketch (Python-style pseudocode)

```python
def optimized_call(user_query, history, kb):
    # 8. semantic response cache
    if (hit := response_cache.lookup(user_query, threshold=0.95)):
        return hit

    # 6. RAG: retrieve only relevant context
    context = kb.retrieve(user_query, k=4)          # token-aware chunks

    # 1/10. compress context and prune few-shot to minimum
    context = compress(context)                      # e.g. LLMLingua

    # 5. manage conversation history to a token budget
    history = fit_to_budget(history, max_tokens=2000)

    # 4. route by difficulty
    model = "small" if classifier(user_query) == "easy" else "large"

    # build prompt: STABLE prefix first (cacheable), volatile last
    messages = [
        system_prompt,          # cached
        *few_shot_examples,     # cached
        *context,               # cached if reused
        *history,
        user_query,             # volatile
    ]

    # 2/11/12. output controls + streaming
    resp = provider.chat(
        model=model, messages=messages,
        max_tokens=400, stop=["</answer>"],
        response_format=SCHEMA, stream=True,
        cache_control="prefix",
    )
    answer = read_until_complete(resp)   # early terminate

    response_cache.store(user_query, answer)
    meter.record(resp.usage)             # 9. feedback loop
    return answer
```

## 5. Measurement & governance

You can't optimize what you don't measure.

- **Instrument every call** — log input tokens, output tokens, cached tokens, model, cost,
  latency, and a request category.
- **Track cost per feature / per user / per request type** — find the expensive hotspots.
- **Set budgets & alerts** — per-tenant token quotas, rate limits, and cost anomaly alerts.
- **Guard against retry storms** — retries and agent loops are a top source of surprise
  bills; cap iterations and back off.
- **A/B test optimizations** — verify that a compression/routing change doesn't degrade
  answer quality (track task success rate alongside cost).
- **Estimate before you build** — `tokens × price × volume` for each planned flow.

### 5.1 Prioritization heuristic

1. Turn on **prompt caching** for any large reused prefix (biggest bang, least effort).
2. **Cap output** (`max_tokens`, terse instructions) — output is the priciest.
3. **Route to a cheaper model** where quality allows.
4. Add **RAG** instead of dumping whole documents.
5. Add **semantic response caching** for repetitive traffic.
6. Introduce **summarization/window management** for long sessions.
7. Consider **fine-tuning/batching** once volume justifies the engineering cost.

## 6. Pitfalls & trade-offs

- **Over-compression hurts accuracy.** Always validate quality after trimming context.
- **Aggressive caching returns stale/wrong answers.** Use conservative similarity
  thresholds and TTLs for time-sensitive data.
- **Truncating history breaks coherence.** Prefer summarization over hard cut-off for
  conversational continuity.
- **Cache-write premium** means caching a rarely-reused prefix can *cost more*.
- **Cheaper models fail silently.** Route with a verifier or confidence check, not blind
  cost-cutting.
- **Optimization has a cost too.** Embeddings, classifiers, and summarization calls consume
  tokens/compute — ensure net savings.

## 7. Summary

Token optimization is a portfolio, not a single trick. The highest-leverage moves —
**prompt caching, output caps, model routing, and RAG** — are low-effort and compound
together. Layer in **semantic response caching, summarization, batching, and eventually
fine-tuning** as volume grows. Above all, **measure everything**: instrument token usage,
attribute cost, and validate that each optimization preserves answer quality. Done well, a
token optimizer layer routinely cuts LLM spend by 50–90% while improving latency and often
answer quality.
