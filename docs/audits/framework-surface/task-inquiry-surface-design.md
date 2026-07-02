# Task, Next-Steps, And Inquiry Surface Design

**Date:** 2026-07-02

**Status:** read-only audit design

## Goal

Clarify the active guidance boundary between operational tasks,
next-step synthesis, durable questions and hypotheses, and inquiry/model
sources. This is a docs-first audit slice. It does not propose CLI behavior
changes yet.

The immediate purpose is to reduce agent confusion around "what should I create
next?" by making each surface's durable role explicit before editing command
docs, skills, or generated Codex mirrors.

## Scope

Review active guidance for:

- `commands/tasks.md`
- `commands/next-steps.md`
- `commands/plan-pipeline.md`
- `commands/sketch-model.md`
- `commands/specify-model.md`
- `commands/add-hypothesis.md`
- relevant user-guide pages:
  - `docs/user-guide/cli-and-workflows.md`
  - `docs/user-guide/agent-workflows.md`
  - `docs/user-guide/epistemic-model.md`
  - `docs/user-guide/entities.md`
- generated mirrors for those command docs in `codex-skills/`

Out of scope for this slice:

- feedback and telemetry surfaces
- dataset/data command surfaces
- broad CLI refactors
- changing command behavior or entity schemas
- cleaning every command that can create tasks incidentally

## Surface Taxonomy

### `tasks`

`science tasks ...` is the durable operational work queue. Use it for concrete
work items with priority, status, blockers, related refs, grouping, and
execution tracking. Task records live in `tasks/active.md` and `tasks/done/`.
They are not equivalent to session-local agent todo tools.

### `next-steps`

`/science:next-steps` is a synthesis and recommendation workflow. Its durable
output is a `type: meta` next-steps analysis under `entities/meta/`. It reads
tasks, commits, questions, hypotheses, plans, results, and prior analyses. It
may offer to create tasks after user acceptance, but the next-steps file is not
the task queue.

### `questions`

`science questions create ...` creates durable open research questions under
`entities/questions/`. Use questions when the project needs to preserve an
uncertainty, research target, or decision-relevant unknown independently of an
immediate task.

`science questions reserve ...` is a specialized concurrency path for parallel
subagents that need to allocate question files without ID races. It should be
documented as an exception, not as the general authoring path.

### `hypotheses`

`science hypotheses create ...` creates durable organizing conjectures under
`entities/hypotheses/`. Use hypotheses when a question has a testable frame,
candidate mechanism, or proposition bundle. The command owns ID sequencing and
frontmatter validation; command docs should not encourage pre-writing the file
or hand-picking IDs except through supported flags.

### `inquiry`

`science inquiry ...` is the source-first model/investigation surface.
`science inquiry init` scaffolds a patch-definition source file under
`entities/patches/`; `show`, `validate`, and export commands read the
materialized graph. Retired graph-mutating inquiry commands still exist as
fail-fast stubs, but active guidance should direct users to edit the inquiry
source and rebuild.

An inquiry is not a generic plan note. Use it when a question or hypothesis
needs variables, boundary roles, flow edges, assumptions, transformations, or
causal/export tooling.

## Initial Findings

### 1. The user guide has the right high-level boundary.

`docs/user-guide/cli-and-workflows.md` already says typed wrappers such as
`questions`, `hypotheses`, `propositions`, and `evidence-lines` are canonical
source-write/read-only surfaces. It also identifies `tasks` as the project task
lifecycle and `inquiry` as source-first inquiry patch profiles.

`docs/user-guide/agent-workflows.md` maps user intent to workflows and CLI
families. The map is concise and consistent with the taxonomy above.

### 2. `next-steps` is conceptually correct but dense.

`commands/next-steps.md` now clearly writes `type: meta` files under
`entities/meta/`, compares prior analyses, audits status drift, and offers to
create tasks from recommendations. The document is long and operationally
detailed, so the main cleanup opportunity is a short boundary statement near
the top:

- next-steps analysis is a recommendation artifact
- task creation happens only after user acceptance
- accepted work belongs in `science tasks ...`

### 3. `tasks` is mostly clear and already warns against session-local task tools.

`commands/tasks.md` clearly states that Science tasks are the authoritative
repo-backed queue and warns against Claude Code's built-in task tools for
Science project tracking. It also defines IDs, statuses, blockers, and related
refs. It is a good anchor for other command docs to cite when they recommend
creating follow-up work.

### 4. `sketch-model` lags the current inquiry source-first guidance.

`docs/user-guide/epistemic-model.md` says the old inquiry graph-mutating
commands are retired and that users should edit the source file and rebuild.
`science/src/science_tool/cli.py` confirms those `inquiry add-*` commands raise
a retired-mutator error.

`commands/sketch-model.md`, however, still tells users to add reusable variables
with `science graph add concept ...` before editing the inquiry block. This is
not merely a stylistic mismatch. `graph add concept` writes directly to
`knowledge/graph.trig`, and `science graph build` / graph materialization
deterministically rebuilds that file from project sources. Concepts added only
through `graph add concept` do not survive a rebuild.

The cleanup should therefore replace `graph add concept` as the durable
sketch-model path, not just label it as another normal option. If any direct
graph mutation remains in the command, it should be explicitly framed as
exploratory and non-durable.

### 5. `specify-model` already distinguishes target and representation.

`commands/specify-model.md` has a useful Step 0 that routes inquiry refs,
hypothesis refs, file-based DAG projects, and proposition decomposition
differently. It already tells file-based DAG projects to skip `graph add
concept` because those graph mutations do not map onto the `.dot` /
`.edges.yaml` file pair.

The residual issue is narrower: the inquiry-patch path still includes
`science graph add concept ...` examples for variable typing. That guidance
should be checked alongside `sketch-model` and either replaced with source-first
patch-source authoring or explicitly marked as exploratory/non-durable.

### 6. `add-hypothesis` is mostly aligned but can emphasize lifecycle earlier.

`commands/add-hypothesis.md` correctly uses `science hypotheses create ...`,
lets the tool assign IDs, and says not to pre-write files or hand-pick IDs
outside supported flags. The setup still puts template reading before the CLI
lifecycle, which may make templates feel like the primary authoring mechanism.
This is lower risk than the inquiry/model issue, because the writing section is
explicitly CLI-first.

### 7. `questions reserve` should be treated as a concurrency exception.

`commands/research-papers.md` uses `science questions reserve ...` and says not
to create files directly because parallel subagents can race on numbering. That
is a legitimate exception to the general `questions create` guidance. The
taxonomy should name it explicitly so future cleanups do not flatten it into an
incorrect one-size-fits-all rule.

## Proposed First Cleanup Slice

Keep the first implementation slice docs-only and behavior-preserving:

1. Add guard tests for active guidance boundaries:
   - `next-steps` states that recommendations become `science tasks` only after
     user acceptance.
   - `sketch-model` does not present retired `inquiry add-*` commands as active
     and does not present durable inquiry work as direct graph mutation.
   - `add-hypothesis` routes creation through `science hypotheses create` and
     does not present template pre-writing as the durable creation path.
   - generated Codex mirrors stay aligned with those source docs.

2. Update source command docs:
   - Add a short taxonomy note to `commands/next-steps.md`.
   - Tighten `commands/sketch-model.md` around source-first inquiry authoring.
   - If needed, clarify `commands/specify-model.md` graph-add examples as
     exploratory or source-backed.
   - Move `commands/add-hypothesis.md` setup wording toward CLI-first
     lifecycle, while still using templates for body-writing after creation.

3. Regenerate generated Codex skills.

4. Skip user-guide edits unless the implementation discovers a concrete gap.
   The core guide already contains the necessary taxonomy.

## Open Questions For The Implementation Plan

1. Should any `science graph add concept ...` example remain in `sketch-model`
   at all? If it remains, it must be explicitly labeled exploratory and
   non-durable because graph materialization rewrites `knowledge/graph.trig`.

2. For standalone durable concept-like records, should the guidance use the
   generic `science entity create <kind> ...` path, which exists today? For
   inquiry-internal variables, the likely source-first home is the
   `entities/patches/<slug>.md` inquiry block rather than a standalone entity.
   The implementation plan should keep those two cases separate.

3. Should the next-steps boundary be duplicated in `commands/plan-pipeline.md`
   Step 6, or is it enough to cite `science tasks add` there as the tracking
   command for accepted plan tasks?

4. Should `questions reserve` get a short user-guide note as a parallel-agent
   exception, or stay local to commands that actually dispatch parallel
   question-authoring work?

## Non-Goals

- Do not remove retired inquiry subcommands in this slice; they fail loudly and
  may be useful compatibility error surfaces.
- Do not change graph build behavior.
- Do not change question, hypothesis, inquiry, or task schemas.
- Do not convert all follow-up-task suggestions across the command tree.
- Do not include feedback/telemetry lifecycle cleanup.

## Acceptance Criteria For The Design

- The taxonomy assigns one primary durable role to each surface.
- Findings are tied to observed source files or CLI behavior.
- The first cleanup slice is narrow enough to implement with focused docs/tests.
- No CLI behavior changes are required before the first implementation plan.
