---
name: prd-compression
description: >-
  Skill 1 of the token-optimizer. Compress a verbose PRD / Jira ticket / feature
  spec into dense, structured "requirement atoms" BEFORE sending it to an LLM,
  cutting input tokens by ~67% with no loss of decision-critical content
  (acceptance criteria are kept verbatim). Use whenever you are about to feed a
  product requirements doc, spec, or ticket into an AI planning/coding call and
  want to reduce token cost. Triggers: "compress this PRD", "shrink this spec",
  "reduce tokens before planning", "optimize this requirements doc".
allowed-tools: Bash, Read
---

# PRD Compression (Skill 1)

Self-contained skill package. Turns a raw, verbose PRD into a compact,
category-grouped set of requirement atoms (GOALS / ACCEPTANCE CRITERIA /
CONSTRAINTS / NON-FUNCTIONAL / DEPENDENCIES / OUT OF SCOPE). Fully deterministic
and offline — no API key, no model.

## Package contents
- [`compressor.py`](compressor.py) — the implementation (`compress_prd`, `render_atoms`).
- [`__init__.py`](__init__.py) — public exports.
- [`test_prd_compression.py`](test_prd_compression.py) — focused tests.

Importable as `prd_compression` (top-level plugin package; see the repo's
`pyproject.toml` `packages.find` roots).

## When to use
- Before any AI feature-planning or code-generation call that takes a PRD, spec,
  or Jira ticket as input.
- When a requirements document is mostly framing (exec summary, background,
  restated goals, hedging) and you want only the decision-relevant content.

## How it works
1. Normalize unicode + strip page/footer boilerplate.
2. Split into units (bullets kept whole; prose split into sentences).
3. Classify each unit into a requirement category; **drop low-signal framing**.
4. Preserve acceptance criteria **verbatim**; tidy hedging/filler from the rest;
   de-dupe near-identical atoms.
5. Re-render as terse bullets grouped by category.

Depends on the core package for shared helpers
(`token_optimizer.optimize.local` / `.tokens`).

## How to run

```bash
tokenopt compress-prd --file path/to/prd.docx
tokenopt compress-prd --file spec.md --out compressed_prd.txt
```

Accepts `.docx`, `.txt`, `.md`, `.log`. Prints the compressed PRD, writes it to
`compressed_prd.txt` (or `--out`), and reports the reduction:

```
PRD: raw=425 tok -> compressed=125 tok (saved 300 tok, 70.6% smaller) | 8 atoms kept, N dropped
```

## Validated outcome
~73% average PRD compression across the 8-case / 2-BU suite (every case ≥ 67%),
acceptance criteria preserved verbatim.

## Related
Pair with [codebase-anchoring](../codebase_anchoring/SKILL.md) and
[model-routing](../model_routing/SKILL.md) (Skill 2).
