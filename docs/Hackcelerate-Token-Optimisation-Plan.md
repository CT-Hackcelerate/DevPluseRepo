# Token Optimisation in AI-Assisted Development
### Hackcelerate Use Case & Development Plan

---

## 1. Executive Summary

AI-assisted development tools (Copilot, Cline, Cursor, Claude Code, etc.) are transforming
how features are built — but every prompt, plan, and code generation cycle consumes
**tokens**, which translate directly into **cost** and **latency**. As teams scale AI usage
across Business Units (BUs), uncontrolled token consumption becomes a significant and
recurring expense.

This project introduces **two complementary skills** that optimise token usage during
feature development, **without sacrificing output quality**:

1. **PRD Compression** — compresses the Product Requirement Document (PRD) input by **~67%**.
2. **Codebase Anchoring + Model Routing** — anchors AI plans to real codebase paths
   (`file:line`) and routes basic tasks to cheaper models.

**Validated Outcome:** Across **8+ A/B tests spanning 2 BUs**, the approach delivers
**up to 35% cost savings** with **equal or higher quality (23/25 quality score)**.

---

## 2. The Problem

| Pain Point | Impact |
|------------|--------|
| Large, verbose PRDs are fed directly into LLMs | High input token cost on every call |
| AI plans reference vague/hallucinated file locations | Wasted regeneration cycles, low trust |
| Every task (trivial or complex) uses the most expensive model | Overspending on simple tasks |
| No measurable quality baseline | Cost cuts risk degrading output |

**Net effect:** Rising AI spend, inconsistent quality, and no data-driven way to prove ROI.

---

## 3. The Solution — Two Skills

### Skill 1 — PRD Compression (67% input reduction)
A preprocessing skill that transforms a raw, verbose PRD into a **dense, structured,
token-efficient representation** before it reaches the LLM.

**Techniques:**
- Strip boilerplate, redundant phrasing, and formatting noise.
- Extract only decision-relevant requirements (goals, constraints, acceptance criteria).
- Convert prose into structured bullet/JSON/YAML "requirement atoms."
- Deduplicate repeated context across sections.
- Preserve semantic completeness — nothing decision-critical is lost.

**Result:** ~67% fewer input tokens per feature-planning call.

### Skill 2 — Codebase Anchoring + Model Routing
A skill that grounds AI output in reality and spends money intelligently.

**Codebase Anchoring (`file:line`):**
- Indexes the repository (symbols, files, line ranges).
- When generating a plan, every step is anchored to a **real path and line number**
  (e.g., `src/services/auth.ts:142`).
- Eliminates hallucinated references → fewer correction/regeneration loops → fewer tokens.

**Model Routing:**
- Classifies each task by complexity (trivial / standard / complex).
- Routes **basic tasks** (formatting, renaming, boilerplate, simple lookups) to a
  **cheaper/faster model**.
- Reserves premium models for genuinely complex reasoning.
- Rule-based + heuristic classifier with a confidence threshold fallback.

---

## 4. How It Works (End-to-End Flow)

```
        ┌─────────────┐
Raw PRD │             │
───────▶│ PRD          │──── compressed PRD (−67% tokens)
        │ Compressor   │           │
        └─────────────┘           ▼
                          ┌──────────────────┐
        Repo Index ──────▶│ Codebase Anchor   │── plan with file:line refs
                          └──────────────────┘           │
                                                          ▼
                                              ┌────────────────────┐
                                Task ────────▶│  Model Router       │
                                              │  (complexity class) │
                                              └────────────────────┘
                                                  │            │
                                          cheap model     premium model
                                                  │            │
                                                  ▼            ▼
                                          ┌──────────────────────────┐
                                          │  Output + Metrics Logger  │
                                          │  (tokens, cost, quality)  │
                                          └──────────────────────────┘
```

---

## 5. Proposed Architecture

```
token-optimizer/
├── skills/
│   ├── prd_compressor/        # Skill 1: PRD compression
│   │   ├── compressor.py
│   │   └── rules.yaml
│   ├── codebase_anchor/       # Skill 2a: file:line anchoring
│   │   ├── indexer.py
│   │   └── anchor.py
│   └── model_router/          # Skill 2b: complexity-based routing
│       ├── classifier.py
│       └── routes.yaml
├── core/
│   ├── llm_client.py          # Unified multi-model client
│   ├── token_counter.py       # tiktoken-based token accounting
│   └── metrics.py             # cost + quality logging
├── eval/
│   ├── ab_runner.py           # A/B test harness (baseline vs optimised)
│   ├── quality_rubric.py      # 25-point quality scoring
│   └── datasets/              # PRD samples from 2 BUs
├── demo/
│   ├── cli.py                 # Live demo entrypoint
│   └── dashboard.py           # Cost/quality visualisation
└── README.md
```

**Suggested stack:** Python, `tiktoken` for token counting, OpenAI/Anthropic SDKs for
multi-model access, a lightweight tree-sitter or `ctags`/ripgrep-based indexer for
codebase anchoring, and Streamlit/Matplotlib for the demo dashboard.

---

## 6. Validation Strategy (A/B Testing)

To prove the **35% cost savings at equal-or-higher quality** claim:

**Setup:**
- **Baseline (A):** Raw PRD → single premium model, no anchoring.
- **Optimised (B):** Compressed PRD → anchored plan → routed models.

**Test matrix:** 8+ real feature requests drawn from **2 different BUs**.

**Metrics captured per run:**
| Metric | How measured |
|--------|--------------|
| Input tokens | `tiktoken` count before/after compression |
| Output tokens | Response token count |
| Cost | tokens × per-model price |
| Quality | 25-point rubric (correctness, completeness, anchoring accuracy, actionability, no hallucination) |
| Latency | Wall-clock time per run |

**Target results:** Up to **35% cost reduction**, quality score **≥ 23/25**
(equal or better than baseline).

---

## 7. Demonstration Plan (Hackcelerate Demo)

The demo will tell a clear before/after story in ~5 minutes:

1. **Show a raw PRD** (verbose, real-world example).
2. **Run the compressor live** → display token count dropping ~67%.
3. **Generate an anchored plan** → highlight real `file:line` references clickable/verifiable.
4. **Trigger the router** → show a trivial task hitting the cheap model and a complex
   task hitting the premium model, with live cost tags.
5. **Open the A/B dashboard** → side-by-side bar charts:
   - Cost: Baseline vs Optimised (−35%)
   - Quality: Baseline vs Optimised (≥ 23/25)
   - Tokens saved across all 8 tests.
6. **Close with the headline:** *"35% cheaper, same or better quality — validated across
   2 BUs."*

---

## 8. Development Roadmap

| Phase | Deliverable | Owner Focus |
|-------|-------------|-------------|
| **Day 1 — Foundation** | Token counter, multi-model LLM client, metrics logger | Core plumbing |
| **Day 1 — Skill 1** | PRD compressor with rule set + validation on sample PRDs | Compression |
| **Day 2 — Skill 2a** | Codebase indexer + `file:line` anchoring | Anchoring |
| **Day 2 — Skill 2b** | Complexity classifier + model router | Routing |
| **Day 3 — Eval** | A/B runner, 25-point quality rubric, run 8+ tests over 2 BUs | Validation |
| **Day 3 — Demo** | CLI demo + dashboard + slide deck | Presentation |

---

## 9. Success Criteria

- ✅ PRD input reduced by **~67%** measurably.
- ✅ 100% of plan steps anchored to **verifiable `file:line`** references.
- ✅ Basic tasks routed to cheaper models with correct classification.
- ✅ **8+ A/B tests** completed across **2 BUs**.
- ✅ **Up to 35% cost savings** demonstrated.
- ✅ Quality maintained or improved (**≥ 23/25**).

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Compression drops critical requirements | Semantic completeness check; keep acceptance criteria verbatim |
| Wrong model routing degrades quality | Confidence threshold → fall back to premium model when unsure |
| Stale codebase index causes bad anchors | Re-index on demand; validate line ranges before emitting |
| Quality scoring subjectivity | Fixed 25-point rubric + blind scoring during A/B tests |

---

## 11. Business Value

- **Direct cost savings** of up to 35% on AI-assisted development spend.
- **Scalable across BUs** — validated on 2, extensible to the whole org.
- **Higher trust** in AI output via verifiable codebase anchoring.
- **Data-driven** — every claim backed by A/B evidence, not anecdote.


