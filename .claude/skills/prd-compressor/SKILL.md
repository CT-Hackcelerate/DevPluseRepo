---
name: prd-compressor
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

# PRD Compressor (Skill 1)

Turns a raw, verbose PRD into a compact, category-grouped set of requirement
atoms (GOALS / ACCEPTANCE CRITERIA / CONSTRAINTS / NON-FUNCTIONAL / DEPENDENCIES /
OUT OF SCOPE). Fully deterministic and offline — no API key, no model.

## When to use
- Before any AI feature-planning or code-generation call that takes a PRD, spec,
  or Jira ticket as input.
- When a requirements document is mostly framing (exec summary, background,
  restated goals, hedging) and you want only the decision-relevant content.

## How it works
1. Normalize unicode + strip page/footer boilerplate.
2. Split into units (bullets kept whole; prose split into sentences).
3. Classify each unit into a requirement category; **drop low-signal framing**.
4. Preserve acceptance criteria **verbatim** (never paraphrase what the build is
   checked against); tidy hedging/filler from the rest; de-dupe near-identical atoms.
5. Re-render as terse bullets grouped by category.

Implementation: [`skills/prd/compressor.py`](../../../src/token_optimizer/skills/prd/compressor.py).

## How to run

```bash
# From the repo root (use run.bat on Windows, or the venv python):
tokenopt compress-prd --file path/to/prd.docx
tokenopt compress-prd --file spec.md --out compressed_prd.txt
```

Accepts `.docx`, `.txt`, `.md`, `.log`. Prints the compressed PRD to stdout,
writes it to `compressed_prd.txt` (or `--out`), and reports the token reduction:

```
PRD: raw=425 tok -> compressed=125 tok (saved 300 tok, 70.6% smaller) | 8 atoms kept, N dropped
```

## Validated outcome
Across the 8-case / 2-BU validation suite: **~73% average PRD compression**
(every case ≥ 67%), with acceptance criteria preserved verbatim. See the
`ab-suite` / `dashboard` commands for the full before/after evidence.

## Related
Pair with [codebase-anchor-router](../codebase-anchor-router/SKILL.md) (Skill 2)
to anchor the resulting plan to real `file:line` references and route the call to
the cheapest capable model.
