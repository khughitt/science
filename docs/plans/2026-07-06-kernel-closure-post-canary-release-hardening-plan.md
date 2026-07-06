# Kernel Closure Post-Canary Release Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify kernel-closure Phase 3b against real downstream projects, then harden live user guidance for the zero-writer boundary.

**Architecture:** Run the toolkit CLI from this branch against real project roots so the tested code is the branch under review while downstream checkouts remain ordinary checkouts. Treat downstream graph output as generated canary evidence: inspect it, then restore it unless a separate downstream migration is explicitly needed. Patch only live toolkit docs, skills, commands, and tests that still imply retired `graph add` writers are durable authoring surfaces.

**Tech Stack:** Python Click CLI, uv-managed `science` package, git worktrees, Markdown docs/commands/skills.

---

### Task 1: Baseline And Canary Matrix

**Files:**
- Create/modify only this plan in `docs/plans/`.
- Do not commit changes in downstream project repositories.

- [x] **Step 1: Verify toolkit baseline for the boundary area**

Run from `science/`:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-tests-post-canary uv run --frozen pytest \
  tests/graph/test_durable_write_boundary.py \
  tests/test_graph_cli.py::test_retired_graph_writer_commands_report_forward_path \
  tests/test_user_guide_docs.py \
  -q
```

Expected: all selected tests pass.

- [x] **Step 2: Record downstream pre-canary status**

Run:

```bash
git -C ~/d/science-commons status --short --branch
git -C ~/d/protein-landscape status --short --branch
git -C ~/d/cancer/cancer-types/multiple-myeloma status --short --branch
```

Expected: record any pre-existing untracked/modified files before canaries.

- [x] **Step 3: Run canaries from the toolkit branch**

Run from `science/`:

```bash
uv run --frozen science validate --profile commit --project-root ~/d/science-commons
uv run --frozen science graph build --project-root ~/d/science-commons
uv run --frozen science validate --profile commit --project-root ~/d/protein-landscape
uv run --frozen science graph build --project-root ~/d/protein-landscape
uv run --frozen science validate --profile commit --project-root ~/d/cancer/cancer-types/multiple-myeloma
uv run --frozen science graph build --project-root ~/d/cancer/cancer-types/multiple-myeloma
```

Expected: commands either pass or produce actionable closure-related findings. If a command fails for a pre-existing project health issue, record the exact failure and continue to the remaining canaries when safe.

- [x] **Step 4: Inspect and restore downstream generated changes**

Run:

```bash
git -C ~/d/science-commons status --short
git -C ~/d/protein-landscape status --short
git -C ~/d/cancer/cancer-types/multiple-myeloma status --short
```

If only generated graph output changed, inspect with `git diff --stat` and restore those generated files after recording the canary result. Do not restore pre-existing untracked files such as `pgdata`.

**Observed canary results (2026-07-06):**

- `science-commons`: `science validate --profile commit` failed on existing scaffold expectations because this shared commons store lacks standard project directories (`entities/`, `doc/`, `knowledge/`, `tasks/`, `code/`, `data/`, `models/`, `results/`) and agent files. `science graph build` passed and created an untracked `knowledge/` directory, which was removed after inspection.
- `protein-landscape`: `science validate --profile commit` failed on existing project-health errors (`dataset.acquired-without-pointer` and `dataset-promotion.datapackage-unresolved`) plus warnings. `science graph build` failed before graph output on an existing authored relation contract error: `conjecture:dark-annotation-lag sci:addresses question:0006-dark-protein-rate-drivers` resolves as `hypothesis -> question`.
- `multiple-myeloma`: `science validate --profile commit` passed with 57 warnings. `science graph build` passed and regenerated `knowledge/graph.trig` plus `knowledge/composite.trig`; both generated files were restored after inspection.

No canary surfaced a kernel-closure regression or a live `graph add` durable-writer dependency. Before the canary, `multiple-myeloma` reported untracked `pgdata`; after the canary and graph-file restore, `git status --short --branch` was clean and `pgdata` was absent. No cleanup command targeted that path.

### Task 2: Live Guidance Sweep

**Files:**
- Likely modify: `docs/user-guide/*.md`, `commands/*.md`, `skills/**/*.md`, `science/tests/test_*docs*.py`.
- Do not edit historical plan files under `docs/plans/historical/` or completed phase plan files unless they are linked as live user guidance.

- [x] **Step 1: Search live guidance for stale durable writer wording**

Run:

```bash
rg -n "science graph add|graph add|durable graph writer|deferred writer|entity create paper <title>" \
  docs/user-guide docs/conventions commands skills templates agents science/tests \
  -g '*.md' -g '*.py'
```

Expected: historical/test assertions may remain, but live guidance must not instruct users to use `graph add` for durable project knowledge.

- [x] **Step 2: Add or update failing docs tests for any stale live guidance**

If stale live guidance exists, add focused assertions to the existing docs tests before editing the docs. Use the nearest existing test module:

```bash
cd science
uv run --frozen pytest tests/test_user_guide_docs.py tests/test_command_docs.py tests/test_codex_skills.py -q
```

Expected before docs edits: the new assertion fails for the stale text.

- [x] **Step 3: Patch live guidance**

Replace stale durable-writer guidance with source-authoring guidance:

```text
Durable project knowledge is authored in source files under entities/ and relation sources; knowledge/graph.trig is compiler-owned generated output.
```

For literature notes, use:

```text
science entity create paper <title> --id <citekey>
```

Expected: no live guide tells users to run `science entity create paper <title>` without `--id <citekey>`.

- [x] **Step 4: Add release note**

Add a concise release/migration note in the existing docs convention location that says:

```text
Kernel closure is complete: durable project graph writes now come only from source declarations compiled by `science graph build`. The old `science graph add` writer surfaces are retired and fail with forward-path guidance.
```

Expected: the note is discoverable from the user guide or release/migration docs.

### Task 3: Verification And Finish

**Files:**
- Any files changed by Task 2.

- [x] **Step 1: Run focused verification**

Run from `science/`:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-tests-post-canary uv run --frozen pytest \
  tests/graph/test_durable_write_boundary.py \
  tests/test_graph_cli.py::test_retired_graph_writer_commands_report_forward_path \
  tests/test_user_guide_docs.py \
  tests/test_command_docs.py \
  tests/test_codex_skills.py \
  -q
uv run --frozen ruff check
uv run --frozen pyright
```

Expected: all pass.

- [x] **Step 2: Run full package verification if code changed**

If Python source changed, run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-tests-post-canary uv run --frozen pytest
cd model && uv run --frozen pytest
```

Expected: all pass.

No Python source changed, so full package pytest was not required. Focused docs/closure tests, `ruff check`, and `pyright` passed.

- [x] **Step 3: Commit toolkit changes**

Run from the worktree root:

```bash
git status --short
git add docs/plans/2026-07-06-kernel-closure-post-canary-release-hardening-plan.md <other changed toolkit files>
git commit -m "docs(kernel-closure): add post-closure canary hardening"
```

Expected: one focused toolkit commit and no downstream project changes.
