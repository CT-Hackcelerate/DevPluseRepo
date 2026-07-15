---
name: model-routing
description: >-
  Skill 2b of the token-optimizer. Classify a task's complexity (trivial /
  standard / complex) with a confidence score and route it to the cheapest
  capable model, reserving premium models for genuinely complex reasoning and
  upgrading toward premium whenever confidence is low. Use when deciding which
  model a task should run on. Triggers: "which model for this task", "route this
  to a cheaper model", "classify this task's complexity", "pick a model tier".
allowed-tools: Bash, Read
---

# Model Routing (Skill 2b)

Self-contained skill package. Deterministic and offline. Spends money
intelligently — cheap models for trivial work, premium only when it's warranted.

## Package contents
- [`classifier.py`](classifier.py) — complexity classifier with a confidence score.
- [`router.py`](router.py) — maps a tier to a model, with the confidence fallback.
- [`__init__.py`](__init__.py) — public exports.
- [`test_model_routing.py`](test_model_routing.py) — focused tests.

Importable as `model_routing` (top-level plugin package).

## How it works
Classifies a task as **trivial / standard / complex** from keyword + structural
signals with a confidence score, then routes:
- trivial → `claude-haiku-4-5` (cheap)
- standard → `claude-sonnet-5`
- complex → `claude-opus-4-8` (premium)

Below the confidence threshold it **upgrades one tier toward premium** — a cheap
model is never chosen on a coin-flip, because a wrong answer costs more in
regeneration than the routing saved.

## How to run

```bash
tokenopt route --task "rename a variable and fix a typo"                 # -> haiku
tokenopt route --task "redesign the auth architecture for concurrency"  # -> opus
```

## Related
The other half of Skill 2 with [codebase-anchoring](../codebase_anchoring/SKILL.md);
runs after [prd-compression](../prd_compression/SKILL.md).
