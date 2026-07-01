# Framework Surface Backlog

## P0: Docs-First Taxonomy

### B1. Add CLI And Workflow Map

**Status:** Addressed by
[`../../user-guide/cli-and-workflows.md`](../../user-guide/cli-and-workflows.md).

**Goal:** Add a durable command taxonomy under `docs/user-guide/`.

**Output:** `docs/user-guide/cli-and-workflows.md` plus index links.

**Acceptance criteria:**

- Lists top-level command families.
- Marks each as canonical, specialized, derived-state, migration-only,
  exploratory, or legacy.
- Documents write class: read-only, source-write, generated-state write,
  external-registry write, or mixed.
- Calls out the dataset/data/data-package/commons dataset distinction.
- Calls out `graph add` as exploratory/manual graph surgery.
- Links from `agent-workflows.md` and `index.md`.

### B2. Add Documentation Placement Rule

**Status:** Addressed in `docs/user-guide/index.md`,
`docs/user-guide/agent-workflows.md`, and `docs/conventions/README.md`.

**Goal:** Make it clear where durable knowledge belongs.

**Output:** Small updates to `docs/user-guide/index.md` and
`docs/conventions/README.md`.

**Acceptance criteria:**

- User guide is for normal operation and concepts.
- Conventions are for stable cross-project rules.
- Process docs are for repeatable maintenance/audit procedures.
- Plans/specs remain temporary design and execution records.

## P1: Command Consistency Contract

### B3. Define CLI Behavior Contract

**Status:** Addressed by
[`../../conventions/cli-behavior.md`](../../conventions/cli-behavior.md), with a
summary link from
[`../../user-guide/cli-and-workflows.md`](../../user-guide/cli-and-workflows.md).

**Goal:** Create a concise contract for future command additions and refactors.

**Output:** A section in `docs/user-guide/cli-and-workflows.md` or a linked
`docs/conventions/cli-behavior.md`.

**Acceptance criteria:**

- Defines preferred path flag names.
- Defines output format expectations.
- Defines report-then-apply and dry-run/apply semantics.
- Defines write classes.
- Defines migration-only and exploratory labeling.
- Gives two or three concrete examples from existing commands.

### B4. Audit Flag Drift

**Status:** Addressed by [`flag-drift.md`](flag-drift.md).

**Goal:** Find concrete option naming drift after the contract exists.

**Output:** Findings table with command, current flags, desired contract, and
recommended action.

**Acceptance criteria:**

- Covers root commands and split CLI modules.
- Does not change behavior.
- Produces a ranked list of low-risk fixes.

## P2: Focused Code Simplification

### B5. Extract One Root CLI Family

**Goal:** Reduce `science/src/science_tool/cli.py` context load without changing
behavior.

**Best candidates:** `tasks`, `dataset`, `datasets`, `feedback`/`telemetry`, or
`project`.

**Acceptance criteria:**

- Moves one cohesive command family to a focused module.
- Keeps command names and behavior unchanged.
- Moves or adds focused tests for that family.
- Leaves root `cli.py` as registration/composition plus genuinely shared root
  behavior.

### B6. Normalize One Command Pattern

**Status:** Started with a CLI workflow-map coverage guard in
`science/tests/test_user_guide_docs.py`. The guard checks the durable taxonomy
against the registered top-level Click commands so new command families do not
silently bypass classification.

**Goal:** Make one repeated behavior consistent across a few commands.

**Best candidates:**

- JSON/table/text output helpers.
- report-then-apply wording.
- project-root resolution.
- read-only command labeling.

**Acceptance criteria:**

- Small helper or documentation-backed test.
- No broad compatibility layer.
- No command renames in the first slice.

## P3: Deeper Design Work

### B7. Dataset Surface Design

**Goal:** Decide whether `data`, `dataset`, `datasets`, `data-package`, and
`commons dataset` need aliases, help-text changes, or regrouping.

**Acceptance criteria:**

- Starts from current docs and actual user workflows.
- Preserves current commands unless there is a clear migration path.
- Names canonical surfaces for new work.
- Names migration-only surfaces and deprecation criteria.

### B8. Annotation Operator Guide

**Goal:** Make the `annotate` subsystem understandable as workflows rather than
a flat list of 25 commands.

**Acceptance criteria:**

- Groups commands by lifecycle phase.
- Separates read-only diagnostics from source/sidecar writes.
- Links stable token conventions without moving everything out of
  `docs/conventions/annotation-tokens.md`.

## Suggested Order

1. B1: CLI and workflow map.
2. B2: Documentation placement rule.
3. B3: CLI behavior contract.
4. B4: Flag drift audit.
5. Choose either B5 or B7 depending on whether the next priority is internal
   simplification or user-facing command clarity.
