---
name: codebase-anchor-router
description: >-
  Skill 2 of the token-optimizer. Two capabilities that ground AI output in
  reality and spend money intelligently: (a) codebase anchoring — resolve every
  plan step to a real file:line reference and flag hallucinated symbols; and
  (b) model routing — classify a task's complexity and route trivial work to a
  cheap model, reserving premium models for genuinely complex reasoning. Use when
  turning a plan into verifiable steps, or when deciding which model a task should
  run on. Triggers: "anchor this plan to the code", "which model for this task",
  "route this to a cheaper model", "verify these steps point at real code".
allowed-tools: Bash, Read
---

# Codebase Anchoring + Model Routing (Skill 2)

Deterministic and offline. Two sub-tools that share one goal — fewer wasted
tokens from hallucinated references and from over-powered models.

## Skill 2a — Codebase anchoring (`file:line`)
Indexes the repository (AST for Python, regex for JS/TS/Java/Go/Ruby/C#) into a
symbol table with exact line numbers, then resolves each plan step's symbol
mentions to a real `path:line` anchor. Steps whose symbol-like terms resolve to
nothing are **flagged as possible hallucinations** rather than silently accepted.

Implementation: [`skills/anchor/indexer.py`](../../../src/token_optimizer/skills/anchor/indexer.py),
[`skills/anchor/anchor.py`](../../../src/token_optimizer/skills/anchor/anchor.py).

```bash
# plan.txt: one plan step per line
tokenopt anchor-plan --plan plan.txt --repo src
```
Prints each step with `[anchored: path:line, ...]` or `[unresolved: term]`, plus
overall anchoring accuracy and a count of steps with unresolved references.

## Skill 2b — Model routing
Classifies a task as **trivial / standard / complex** from keyword + structural
signals with a confidence score, then routes:
- trivial → `claude-haiku-4-5` (cheap)
- standard → `claude-sonnet-5`
- complex → `claude-opus-4-8` (premium)

Below the confidence threshold, it **upgrades one tier toward premium** — a cheap
model is never chosen on a coin-flip, because a wrong answer costs more in
regeneration than the routing saved.

Implementation: [`skills/router/classifier.py`](../../../src/token_optimizer/skills/router/classifier.py),
[`skills/router/router.py`](../../../src/token_optimizer/skills/router/router.py).

```bash
tokenopt route --task "rename a variable and fix a typo"          # -> haiku
tokenopt route --task "redesign the auth architecture for concurrency"  # -> opus
```

## Validated outcome
In the 8-case / 2-BU A/B suite, anchoring + routing (on top of PRD compression)
delivers **up to ~58% cost savings at equal-or-higher quality (avg 24/25)**.
Verify with:

```bash
tokenopt ab-suite --repo src          # prints per-case + aggregate deltas
tokenopt dashboard --repo src         # writes ab_dashboard.html (charts)
```

## Related
Run after [prd-compressor](../prd-compressor/SKILL.md) (Skill 1): compress the
PRD, generate a plan, anchor it here, and route the call to the right model.
