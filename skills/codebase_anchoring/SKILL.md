---
name: codebase-anchoring
description: >-
  Skill 2a of the token-optimizer. Ground an AI plan in reality: index a
  repository (AST for Python, regex for JS/TS/Java/Go/Ruby/C#) and resolve every
  plan step's symbol mentions to a real file:line reference, flagging unresolved
  (hallucinated) symbols rather than silently accepting them. Use when turning a
  plan into verifiable steps or checking that steps point at real code. Triggers:
  "anchor this plan to the code", "verify these steps point at real code",
  "find file:line for these symbols", "check for hallucinated references".
allowed-tools: Bash, Read
---

# Codebase Anchoring (Skill 2a)

Self-contained skill package. Deterministic and offline. Eliminates wasted tokens
from hallucinated code references and the regeneration loops that follow them.

## Package contents
- [`indexer.py`](indexer.py) — repo symbol index with exact `file:line` locations.
- [`anchor.py`](anchor.py) — resolves plan steps to anchors; flags hallucinations.
- [`__init__.py`](__init__.py) — public exports.
- [`test_codebase_anchoring.py`](test_codebase_anchoring.py) — focused tests.

Importable as `codebase_anchoring` (top-level plugin package).

## How it works
Indexes the repository (AST for Python, regex fallback for JS/TS/Java/Go/Ruby/C#)
into a symbol table with exact line numbers, then resolves each plan step's
symbol mentions to a real `path:line` anchor. Steps whose symbol-like terms
resolve to nothing are **flagged as possible hallucinations**.

## How to run

```bash
# plan.txt: one plan step per line
tokenopt anchor-plan --plan plan.txt --repo src
```

Prints each step with `[anchored: path:line, ...]` or `[unresolved: term]`, plus
overall anchoring accuracy and a count of steps with unresolved references.

## Related
Runs after [prd-compression](../prd_compression/SKILL.md); pairs with
[model-routing](../model_routing/SKILL.md) as the two halves of Skill 2.
Validated (with routing) at ~58% cost savings, 24/25 quality across the A/B suite.
