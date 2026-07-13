# Feedback Small Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Address a small batch of recent Science feedback without taking on the larger design-sized items.

**Architecture:** Keep behavior changes in the existing command modules. `prose_lint.py` owns short-form token classification, `explore_ideas.py` owns report validation/planning, and `cli.py` exposes the new check-only mode. Command markdown stays the source for the generated Codex skill mirror.

**Tech Stack:** Python 3.13, Click, pytest, uv, markdown command mirrors.

**Status update 2026-07-13:** Completed on merged branch
`feedback-2026-07-validate-explore` at commit `09010805 fix(feedback): close
validate and explore-ideas frictions`. This plan was recovered from the stale
worktree and checked into `main` during cleanup after confirming the
implementation is already present in the main checkout.

---

### Task 1: Short-Form Biomedical Exemptions

**Files:**
- Modify: `science/tests/test_prose_lint.py`
- Modify: `science/src/science_tool/prose_lint.py`
- Modify: `docs/conventions/prose-lints.md`

- [x] Add failing tests showing `D1`, `H3`, and reagent/timepoint phrasing do not trigger `short-form-ids`, while `Q1`, `h05`, and `t088` still do.
- [x] Run `PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest tests/test_prose_lint.py::TestShortFormIds -q` and verify the new tests fail.
- [x] Add narrow context-aware exemptions in `detect_short_form_ids`.
- [x] Rerun the same test target and verify it passes.
- [x] Update the prose-lints convention doc to describe the built-in biomedical-context skips.

### Task 2: `explore-ideas apply --check`

**Files:**
- Modify: `science/tests/test_explore_ideas_apply.py`
- Modify: `science/src/science_tool/explore_ideas.py`
- Modify: `science/src/science_tool/cli.py`
- Modify: `commands/explore-ideas.md`
- Regenerate: `codex-skills/science-explore-ideas/SKILL.md`

- [x] Add failing tests that `--check` validates and reports counts without writing entities or mutating the report, and that JSON output is valid.
- [x] Run `PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest tests/test_explore_ideas_apply.py -q` and verify the new tests fail.
- [x] Add a plan-only function that reuses parse, ref resolution, and `plan_report`, then expose it through `--check`.
- [x] Rerun the explore-ideas tests and verify they pass.
- [x] Document `--check` in the command markdown and regenerate Codex skill mirrors with `python scripts/generate_codex_skills.py`.

### Task 3: Plan-Pipeline Decision Guidance

**Files:**
- Modify: `commands/plan-pipeline.md`
- Regenerate: `codex-skills/science-plan-pipeline/SKILL.md`

- [x] Remove `decision:<id>` from `related:` guidance and examples.
- [x] State that decisions live in `core/decisions.md` and should be referenced in prose or a non-graph plan header note.
- [x] Regenerate Codex skill mirrors.

### Task 4: Verification

- [x] Run `PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest tests/test_prose_lint.py tests/test_prose_lint_cli.py tests/test_explore_ideas_apply.py -q`.
- [x] Run `PYTEST_DEBUG_TEMPROOT=/tmp uv run --frozen pytest tests/test_codex_skills.py -q`.
- [x] Run `uv run --frozen ruff check`.
- [x] Inspect `git diff --stat` and `git diff --check`.
