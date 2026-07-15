# Prompts Used to Build TokenOptimizer

> **Note on provenance.** This is a reconstruction of the prompts that drove the
> development of TokenOptimizer, inferred from the git history, commit messages,
> and the documents in `docs/`. It is not a verbatim chat transcript — it
> captures the *intent* of each development phase in prompt form so the build can
> be understood, reviewed, or replayed. Phases map to the actual commit timeline
> (2026-07-08 → 2026-07-15).

---

## Phase 0 — Concept & Plan

1. "We're entering Hackcelerate. Help me design a use case around **token
   optimisation in AI-assisted development**. The idea: AI coding tools burn
   tokens on every prompt/plan/generation, which is real cost and latency at BU
   scale. Propose two complementary skills that cut token usage *without* losing
   output quality, and write a full development plan with problem statement,
   architecture, validation strategy, roadmap, success criteria, and business
   value."

2. "Make the two skills concrete: **(1) PRD Compression** targeting ~67% input
   reduction, and **(2) Codebase Anchoring + Model Routing** — anchor every plan
   step to a real `file:line` and route trivial tasks to a cheaper model.
   Set the validated target at **up to 35% cost savings** across **8+ A/B tests
   over 2 BUs**, with quality held at **≥ 23/25**."

3. "Save this as the Hackcelerate plan doc and commit it."

---

## Phase 1 — Core Offline Pipeline

4. "Start the implementation. Build a Python package with an **offline
   optimization pipeline**: local text reductions, **tiktoken-based token
   counting**, and an **extractive summarizer** — so it works with no API key."

5. "Add a **config layer** and **local-model summarization** so the tool can run
   fully offline, and expand the test suite to cover it."

6. "Add a **CLI** (`tokenopt`) and a run-logging mechanism; write the run logs to
   `logs/` and gitignore them."

7. "Combine the repo READMEs into one — DevPluseRepo title plus the full
   TokenOptimizer docs — and inline the Token-Optimizer reference guide as an
   appendix."

---

## Phase 2 — Bug Fixes & Hardening

8. "There's a regression in offline `--summarize` — the ordering is wrong. Fix it,
   and make summarize **default-on when offline**."

9. "Add the Jira issue sample and a sample document for demos; tidy the UI."

10. "Update the Claude Code settings / permission allowlist so git commands don't
    prompt every time."

---

## Phase 3 — Feature-Dev Skills, A/B Tooling & Dashboard

11. "Surface the two feature-dev skills as real commands, not just library code:
    - `tokenopt compress-prd` (compress a PRD into dense requirement atoms, keep
      acceptance criteria verbatim),
    - `tokenopt anchor-plan` (anchor plan steps to real `file:line`, flag
      hallucinated symbols),
    - `tokenopt route` (classify task complexity, route to the cheapest capable
      model with a confidence-threshold fallback)."

12. "Add an **A/B validation harness** (`tokenopt ab-suite`) that runs the
    8-case / 2-BU baseline-vs-optimised comparison, and a **dashboard**
    (`tokenopt dashboard`) that renders results to a **self-contained HTML page**
    with inline SVG and zero dependencies."

13. "Package the skills as **Claude Code skills** with `SKILL.md` wrappers around
    the CLI."

14. "Build the **desktop UI**: add a **Feature-Dev Skills** tab (card grid + shared
    result console) and a **Dashboard** tab (KPI tiles + native Tk-canvas bar
    charts, Run A/B & Refresh, Open HTML Dashboard). Add tab traversal, size the
    window to the display work area, and a `TOKENOPT_UI_TAB` launch hook."

15. "The A/B numbers look off — our sample PRDs were already terse (~13%
    compression). Make the **validation dataset realistic** (add executive
    summary, background, stakeholders, revision history, appendix framing) so
    compression measures ~73% (≥67% each case), without changing the requirement
    atoms."

16. "Add **regression tests** that lock the headline claims: every PRD compresses
    ≥ 67%, and the A/B suite meets ≥ 35% savings at ≥ 23/25 quality."

---

## Phase 4 — Enterprise Restructure

17. "Restructure into an **enterprise layered layout** — move `config`, `run_log`,
    `llm` under `core/`; skills under `skills/`; `eval/` → `evaluation/`; `ui.py`
    → `ui/app.py`. Use `git mv` to preserve history and update every import,
    entry point, and test. No functional regressions."

18. "Rename **Hackathon → Hackcelerate** project-wide."

19. "Later, **extract the three skills to top-level plugin packages** — a
    decoupled `skills/` tree where each skill is a self-contained package (code +
    `SKILL.md` + tests): `prd_compression`, `codebase_anchoring`, `model_routing`.
    Register them in `pyproject.toml` and update all imports/tests."

---

## Phase 5 — Demo, Deck & Documentation

20. "Add a **Guided Demo** to the UI (Help → Guided Demo): an automated,
    video-style walkthrough that auto-advances through narrated scenes, switches
    tabs, and runs each feature live (compress / route / anchor / dashboard) with
    Prev/Pause/Next/Close controls and a `TOKENOPT_UI_DEMO=1` auto-start."

21. "Add an **in-UI Anthropic API key** field on the Document source so a user can
    opt into Claude (Haiku) summarization + exact token counts at runtime; update
    the header mode chip live; blank falls back to `.env` or fully offline."

22. "Give the guided demo a **voice-over**, and move the launcher to a header
    button."

23. "Produce a **narrated demo video** (`docs/TokenOptimizer-Demo.mp4`) — a
    voice-over walkthrough of every feature using SAPI TTS + ffmpeg, with a
    generator script."

24. "Build the **Hackcelerate pitch deck** (`.pptx`) with a live A/B chart, the
    embedded dashboard, and a demo-video slide, via a generator script."

25. "Rewrite `docs/FEATURES.md` (skills, validation, UI tabs, project layout),
    update the README with a skills/validation section, and add a `CHANGELOG.md`."

26. "Write an **Architectural Design Document** (PDF) covering layers, components,
    runtime flows, cross-cutting concerns, and design-decision rationale, with a
    generator script."

27. "Add **PlantUML workflow diagrams** and embed them in the Architecture Design
    Document."

---

## Cross-cutting / recurring prompts

- "Keep it working **fully offline** — everything must degrade gracefully with no
  API key."
- "Run the test suite and make sure nothing regresses." (Offline suite grew from
  early tests to **68 passing**.)
- "Commit this / open a PR." (PRs #1–#5 on the feature branches.)

---

*Generated 2026-07-15. If you have the original chat logs, this file can be
updated to match them verbatim.*
