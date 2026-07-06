# Dataset Surface Design

**Date:** 2026-07-01
**Reviewed:** 2026-07-02

**Status:** Historical design note; `science data-package ...` was retired on
2026-07-06.

## Scope

This design covers the Science dataset/data command surface and the durable
guidance that teaches agents which command to use. It is intentionally
docs-first: no command renames, removals, aliases, or behavior changes are part
of this first slice.

In scope:

- `science data audit`
- `science dataset ...`
- `science datasets ...`
- `science commons dataset ...`
- `science commons data ...`
- user-guide, convention, command, and skill guidance that references those
  surfaces

Out of scope for the first implementation slice:

- command regrouping or deprecation mechanics
- new dataset model fields
- broad migration of existing project data
- commons package-manager behavior
- direct changes to generated Codex skill output except through its source
  command/skill guidance or generator tests

## Problem

The current command names encode real lifecycle layers, but those layers are
easy to confuse:

| Surface | Current role |
|---|---|
| `science data audit` | Audits tracked-source vs ignored-payload data boundaries. |
| `science dataset ...` | Manages local Science dataset entity records and their lifecycle. |
| `science datasets ...` | Searches external repositories and operates on datapackage/runtime artifacts. |
| `science commons dataset ...` | Builds and validates commons-born dataset packages. |
| `science commons data ...` | Resolves commons bulk-data payload paths. |

The distinction is mostly documented, but not always where agents make command
choices. The user guide has a strong model description in
`docs/user-guide/entities.md`; the command taxonomy has a concise distinction in
`docs/user-guide/cli-and-workflows.md`; agent-facing workflow guidance lives in
`commands/catalog-datasets.md`, `commands/find-datasets.md`, and
`commands/plan-pipeline.md`; lower-level data conventions live under
`skills/data/`.

This is not only a theoretical naming concern. Current guidance still contains
stale or ambiguous examples:

- `commands/plan-pipeline.md:149` names a "future `science dataset verify`"
  command, but the current command is `science dataset verify-access`.
- `commands/find-datasets.md` still treats direct emission of
  `entities/datasets/<slug>.md` as the default documentation path, even though
  routine external dataset records now have `science dataset add` and
  `science dataset verify-access`.
- `commands/find-datasets.md` also still starts from legacy `specs/`
  locations before the layout-v3 entity roots used by newer guidance.

Those examples can make agents choose the wrong layer: hand-authoring dataset
files instead of using `science dataset add`, using plural `datasets` for local
entity lifecycle work, using legacy `data-package` language for current dataset
entities, or skipping the access-verification gate before pipeline planning.

## Design Principles

1. Keep the existing command names for now. They are established and encode
   useful distinctions once the lifecycle is visible.
2. Make the canonical boundary explicit at every decision point:
   - singular `dataset` for Science dataset entities;
   - plural `datasets` for external discovery and datapackage/runtime tooling;
   - `data audit` for tracked/ignored file-boundary checks;
   - `data-package` for legacy migration only;
   - `commons dataset` and `commons data` for shared commons operations.
3. Prefer guidance and help-text tightening before adding aliases. Aliases can
   reduce local friction but also add another surface for agents to learn.
4. Keep model detail in the user guide, workflow order in command docs, and
   reusable data-management rules in skills.
5. Treat generated Codex skills as downstream artifacts of command/skill source
   guidance. Source docs and generator tests should drive generated output.

## Escalation Signal

The first implementation slice deliberately bets that guidance can carry the
existing command names. That bet should be treated as falsifiable. After the
guidance cleanup, move to a naming/help-text design if either of these is true:

- source guidance and generated Codex skills are aligned, but a review of
  `commands/`, `skills/`, and generated `codex-skills/` still finds agents being
  told to use plural `science datasets` commands for local dataset entity
  lifecycle work, or singular `science dataset` commands for repository/runtime
  datapackage work;
- the next dataset-focused agent workflow or feedback record still shows the
  same command-selection error after it has loaded the updated command/skill
  guidance.

If that happens, the next design should consider command-help changes first and
then aliases or regrouping. It should not keep polishing prose around a name
collision that the command surface itself is causing.

## Canonical Workflow Map

### 1. Data Boundary Inspection

Use `science data audit` when the question is about whether project files are in
the right tracked or ignored location. It does not create dataset entities and
does not inspect repository search results.

Primary durable guidance:

- `docs/conventions/data-boundary.md`
- `docs/conventions/cli-behavior.md`
- `docs/user-guide/cli-and-workflows.md`

### 2. Dataset Discovery

Use `science datasets search`, `science datasets metadata`, and
`science datasets files` when the subject is an external repository, accession,
or downloadable file listing. Discovery should feed a dataset-entity workflow;
it should not be the final durable project record.

This is one of two roles currently inside the plural `datasets` group. It is
adapter/repository-facing, not runtime-package-facing.

Primary durable guidance:

- `commands/find-datasets.md`
- `commands/catalog-datasets.md`
- `docs/user-guide/entities.md`

### 3. Local Dataset Entity Lifecycle

Use `science dataset add`, `science dataset verify-access`,
`science dataset link`, `science dataset reconcile-links`,
`science dataset prioritize`, `science dataset show`, and related singular
commands when the subject is a local `dataset:<slug>` entity under
`entities/datasets/`.

This is the canonical durable authoring surface for external and derived
dataset records. Agents should not hand-author routine dataset entities unless
the CLI lacks the required field or a project-specific template is explicitly
needed for review.

Primary durable guidance:

- `docs/user-guide/entities.md`
- `commands/catalog-datasets.md`
- `commands/plan-pipeline.md`
- `commands/review-pipeline.md`

### 4. Runtime Datapackage And QA Tooling

Use `science datasets validate`, `science datasets infer-schema`,
`science datasets qa`, `science datasets download`, and
`science datasets hydrate-worktree` when operating on runtime descriptors,
resource schemas, downloaded files, QA reports, or ignored payload hydration.

These commands are adjacent to dataset entities but do not replace them. A
pipeline should resolve an input to `dataset:<slug>` first, then use plural
`datasets` commands for the runtime package work.

This is the second role currently inside the plural `datasets` group. If a
later regrouping is needed, the discovery/runtime split inside `datasets` is a
stronger boundary than the singular/plural distinction by itself.

Primary durable guidance:

- `docs/user-guide/entities.md`
- `skills/data/SKILL.md`
- `skills/data/frictionless.md`
- `skills/pipelines/snakemake.md`

### 5. Derived Dataset Registration

Use `science dataset register-run` after a workflow run has declared outputs and
produced runtime datapackages. Derived datasets are machine-authored from
workflow metadata and should not be emitted by discovery commands.

Primary durable guidance:

- `docs/user-guide/entities.md`
- `commands/plan-pipeline.md`

### 6. Commons Reuse

Use `science commons dataset ...` for commons-born reusable dataset packages and
`science commons data resolve` for resolving bulk payload paths in the commons
store. Project-local work should continue to reference reusable datasets by
`dataset:<slug>` and use overlays for project-specific context.

Primary durable guidance:

- `docs/user-guide/cross-project-work.md`
- `docs/process/pipeline-audit-and-refactor.md`
- `commands/catalog-datasets.md`

### 7. Legacy Data-Package Cleanup

The former `science data-package ...` migration surface was retired after the
registered-project inventory reported zero legacy data-package entity findings.
New work should use `dataset:<slug>` entities, runtime datapackages, and
research packages as appropriate.

Primary durable guidance:

- `docs/user-guide/cli-and-workflows.md`
- `docs/user-guide/entities.md`
- validation diagnostics that require explicit dataset owners with
  `datapackage:` pointers

## Guidance Surfaces To Curate

| Surface | Current disposition | Required cleanup direction |
|---|---|---|
| `docs/user-guide/cli-and-workflows.md` | Good concise command map. | Keep as the top-level command boundary; add enough wording that agents can choose the right layer without reading the full entities chapter. |
| `docs/user-guide/entities.md` | Strong model/lifecycle reference. | Keep as the canonical dataset model and lifecycle chapter; avoid burying CLI boundary rules only here. |
| `docs/conventions/data-boundary.md` | Good convention for tracked vs ignored data. | Update examples to current option contract if needed, but keep scope limited to file-boundary policy. |
| `docs/user-guide/cross-project-work.md` | Good commons-born dataset overview. | Link back to the dataset lifecycle boundary so commons docs do not look like the default local path. |
| `commands/catalog-datasets.md` | Current and detailed front-half dataset workflow. | Keep as the primary agent workflow for gap scan, discovery, verification, connection, prioritization, and plan handoff. |
| `commands/find-datasets.md` | Useful discovery workflow, but still contains older direct-file authoring and legacy `specs/` assumptions. | Recast as discovery-only or subordinate to `catalog-datasets`; route durable records through `science dataset add` / `verify-access` / `link`. |
| `commands/plan-pipeline.md` | Strong data-access and reproducibility gate. | Replace stale "future `science dataset verify`" wording at the data-access gate (`commands/plan-pipeline.md:149` at audit time) with the current `science dataset verify-access` surface; keep the gate strict. |
| `commands/review-pipeline.md` | Checks dataset lifecycle contract. | Ensure it points to the same singular/plural boundary and access gate wording. |
| `skills/data/SKILL.md` | Core data conventions, but "new data source" still implies manual template authoring and `science.yaml` edits. | Point routine dataset entity creation at `science dataset add`; reserve manual authoring for unsupported/project-specific cases. |
| `skills/data/frictionless.md` | Good datapackage guidance. | Clarify that Frictionless descriptors are runtime/package artifacts and `science dataset` remains the entity lifecycle. |
| `skills/pipelines/snakemake.md` | Uses plural `datasets` commands for acquisition/validation. | Keep, but cross-link to the dataset entity gate when pipeline inputs are project datasets. |
| `codex-skills/` | Generated command-skill output. | Do not hand-edit as primary source; update source commands/skills and generator tests so generated output stays aligned. |

## Recommended First Implementation Slice

The first implementation should be a guidance cleanup, not a behavior change:

1. Update `commands/find-datasets.md` so it is clearly a discovery support
   command. Durable project records should be created or updated through the
   singular `science dataset` lifecycle commands, not by manually writing
   `entities/datasets/<slug>.md` as the default path.
2. Update `commands/plan-pipeline.md` and `commands/review-pipeline.md` to refer
   to `science dataset verify-access` consistently.
3. Update `skills/data/SKILL.md` and `skills/data/frictionless.md` so skills
   distinguish dataset entities from datapackage/runtime descriptors.
4. Tighten `docs/user-guide/cli-and-workflows.md` and cross-links in
   `docs/user-guide/entities.md` / `docs/user-guide/cross-project-work.md` only
   when there is a concrete guardable ambiguity, such as missing singular vs
   plural boundary text, missing legacy `data-package` labeling, or commons
   guidance that does not point back to the project-local dataset lifecycle.
5. Regenerate `codex-skills/` from the updated command and skill sources and
   commit the generated mirrors with the source guidance changes.
6. Add or adjust tests that guard the key guidance strings in
   `science/tests/test_command_docs.py` and `science/tests/test_codex_skills.py`.

If, after that cleanup, command help still looks ambiguous in normal
`science --help` flows, a second implementation slice can make targeted
help-text changes. Aliases or regrouping should remain a separate design
decision.

## Acceptance Criteria

- The user guide states the singular/plural dataset boundary near the command
  taxonomy and links to detailed lifecycle docs.
- Agent command guidance routes durable dataset records through
  `science dataset add`, `science dataset verify-access`,
  `science dataset link`, and `science dataset prioritize`.
- Discovery guidance uses `science datasets ...` only for repository/runtime
  discovery and metadata/file inspection.
- Pipeline guidance resolves every input to a `dataset:<slug>` entity and names
  `science dataset verify-access` as the current verification command.
- Data skills explain that datapackages are runtime/package descriptors, not the
  local dataset entity lifecycle.
- Tests guard that `commands/find-datasets.md` no longer presents direct
  `entities/datasets/<slug>.md` authoring as the routine path when
  `science dataset add` / `verify-access` can express the record.
- Tests guard that `commands/plan-pipeline.md` names
  `science dataset verify-access`, not stale `science dataset verify`, in the
  data-access gate.
- The legacy `science data-package` command is not part of the active command
  surface.
- The generated `codex-skills/science-catalog-datasets/SKILL.md`,
  `codex-skills/science-find-datasets/SKILL.md`, and
  `codex-skills/science-plan-pipeline/SKILL.md` reflect the same source
  guidance after regeneration.
- Generated Codex skill tests protect the same guidance after regeneration.
- No command behavior changes are required in the first slice.

## Open Questions For Later Slices

- Should the discovery commands currently under `science datasets`
  (`search`/`metadata`/`files`) eventually move under a clearer
  external-source surface?
- Should the runtime/package commands currently under `science datasets`
  (`validate`/`infer-schema`/`qa`/`download`/`hydrate-worktree`) eventually move
  under a clearer datapackage or runtime-data surface?
- Should dataset entity lifecycle commands move from the root CLI into a
  focused `dataset_cli.py` module before or after any help-text cleanup? The
  existing `science_tool/data_cli.py` extraction is the closest local precedent.
- Should commons dataset workflows get a dedicated operator guide once
  package-manager behavior exists?
