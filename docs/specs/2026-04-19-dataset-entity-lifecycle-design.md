# Dataset Entity Lifecycle and `science-pkg` Schema

**Date:** 2026-04-19
**Status:** Draft (rev 2.2 — adds plan-review clarifications: parallel-runs lifecycle, model-level invariants, single canonical loader)
**Supersedes:** rev 1 of this file (external-dataset-only access verification gate)
**Revision history:**
- rev 2 — unified `dataset` entity covering external + derived (`origin:` discriminator); science-pkg schema family; `data-package` → `research-package` rename.
- rev 2.1 — design-review fixes: ship `data-package migrate` in v1; per-output runtime datapackages; entity-vs-runtime ownership table (entity drops `resources[]`); plan gate vs runtime stageability split (Dim 3 escalates); `outputs[].resource_names` (renamed); symmetric research-package backlinks (invariant #11).
- rev 2.2 (this rev) — plan-review clarifications: parallel derived datasets per `(workflow, run, output)` tuple coexist; per-output runtime datapackages are *views* into the run-aggregate (resources stay in place, `basepath: ".."`); model-level invariant enforcement at Pydantic construction (not only JSON Schema); single canonical loader (`parse_entity_file` extended, not parallel function); recursion-safe transitive gate walk; comment-preserving frontmatter edits.
**Related (forward):** `docs/specs/2026-04-19-multi-backend-entity-resolver-design.md` (Spec Y, sibling — written immediately after this one)

## Motivation

Two adjacent problems share one root cause: the framework lacks a single authoritative representation for "data the project depends on."

**Problem 1 — External dataset access is verified too late.**
Every research project has external data inputs (papers, public databases, supplementary tables). The point at which access to those inputs should be verified is **before detailed pipeline planning begins** — discovering that a dataset is actually controlled-access mid-implementation forces scope decisions under time pressure, invalidates in-progress work, and leaves the project without a durable record of what was tried. The framework's `templates/dataset.md` defines the entity but treats `access: public | controlled | mixed` as aspirational discovery-time metadata rather than a verified gate; `commands/plan-pipeline.md` has no explicit data-access gate; `commands/review-pipeline.md` Dim 3 checks that a source is "specified" but not that its access has been **verified**.

The concrete case that triggered Problem 1: a cbioportal task (t111) discovered mid-implementation that Xu 2025's per-variant calls were dbGaP-only despite the paper being published. A post-hoc data-access gate was added to the task's plan document — a one-off file with a bespoke format. The insight is that this information belongs on the dataset entity itself, not in a sibling plan artefact.

**Problem 2 — Workflow-generated data lives in a parallel entity universe.**
The 2026-03-30 provenance spec introduced `data-package` entities for workflow outputs: a Frictionless `datapackage.json` plus narrative bundle (cells, figures, prose, vega-lite specs, code excerpts). External datasets and workflow-generated datasets — both are "data the project consumes" — sit in two unrelated entity types with two unrelated schemas. A plan that consumes a public supplement and a workflow output reasons about them as different kinds of thing. Backlinks (`consumed_by`), gate state, ontology semantics, runtime resource manifests are duplicated, partially-implemented, or entirely absent on one side or the other.

**The unification.**
Both classes are *data*. Provenance differentiates *where the data came from*, but otherwise the metadata model is identical: identity, title, ontology terms, resource paths and hashes, schemas, formats, downstream consumers. This spec adopts a single schema family — the **`science-pkg`** profile of Frictionless DataPackage — and a single unified `dataset` entity type covering both external and derived data, discriminated by `origin: external | derived`.

A separate, narrower entity (`research-package`, renamed from `data-package`) carries the narrative-rendering bundle (cells, figures, prose, vega-lite, code excerpts) and *displays* one or more derived datasets. The data half and the rendering half are now distinct concerns.

## Goal

Establish `science-pkg` (Frictionless DataPackage + science-specific extensions) as the single schema family for all data the project consumes — external sources and workflow outputs alike. Extend the `dataset` entity to be the single authority for both branches and route `/science:plan-pipeline`, `/science:review-pipeline`, and `/science:find-datasets` through a unified resolver. Every external data input resolves to a `dataset:<slug>` entity (`origin: external`) with a verified access gate; every workflow output resolves to a `dataset:<slug>` entity (`origin: derived`) with a transitive derivation chain. Both share the same `consumed_by` backlink, the same on-disk Frictionless representation, and the same review/health machinery.

The original `data-package` entity is split: its *data* half folds into derived `dataset` entities; its *narrative* half becomes `research-package`, which `displays:` one or more derived `dataset` entities.

## Design Principles

Carried forward from rev 1, extended for unification:

- **The dataset entity is the authority for project-level metadata; the runtime `datapackage.yaml` is the authority for resource-level metadata.** No duplicated truth. The two surfaces share the science-pkg schema family; drift between them is a `science-tool health` warning.
- **One schema family for both origins.** External and derived datasets validate against the same `science-pkg` JSON Schema. `origin: external | derived` is the discriminator; sibling top-level blocks (`access:` for external, `derivation:` for derived) are mutually exclusive.
- **Access state is structured + dated** (external only). `access.verified: true|false`, `access.verification_method` (`retrieved` vs `credential-confirmed`), `access.last_reviewed`. No state machine beyond those three fields; `last_reviewed` is a soft staleness signal.
- **Derivation state is structured + symmetric** (derived only). `derivation.workflow_run` points at a `workflow-run` entity whose `produces:` field MUST list this dataset (symmetric edge). `derivation.inputs` lists upstream `dataset:<slug>` entities and is enforced transitively by the gate.
- **Branch decisions are machine-readable.** A Branch-B outcome (scope-reduce / expand / substitute) for an external dataset is recorded in a structured `access.exception:` block, not only in prose. The prose log remains for narrative; rubric checks read the structured form.
- **Granularity follows artefact, not source.** External: a paper with one public supplement and one controlled raw-read deposit produces two sibling dataset entities linked via `parent_dataset`. Derived: one entity per *logical output* of a workflow run (a sharded Parquet is one dataset; two unrelated CSVs are two), declared explicitly by the workflow's `outputs:` block.
- **Plans consume dataset entities by stable ID, regardless of origin.** `/science:plan-pipeline` and `/science:review-pipeline` resolve inputs through `dataset:<slug>` references with no per-origin special-casing. Unknown external inputs dispatch to `/science:find-datasets`; unknown derived inputs halt with "register the producing run."
- **Execution reads from `datapackage.yaml`, not from discovery URLs.** `access.source_url` (external) is for verification and first-time retrieval; `derivation.workflow_run` (derived) identifies the producing run. Once a `datapackage.yaml` exists at the runtime path, pipeline execution consumes its enumerated resources.
- **No silent fallback on gate state.** External: `access.verified: false` without `access.exception` halts the gate. Derived: missing/asymmetric workflow-run or unverified transitive input halts the gate. Matches the framework's general fail-early posture.
- **Prose stays human-authored.** Verification logs, granularity notes, narrative remain markdown prose — structured where it pays (frontmatter, exception block), unstructured where it doesn't (log entries).
- **Forward-compatible with multi-backend storage (Spec Y).** This spec commits only to markdown-as-source for the entity surface. Spec Y will generalize entity storage so any entity type can adopt other backends (datapackage-directory, aggregate-json). The science-pkg schema is identical regardless of backend.

## Scope

### In scope (v1)

- A `science-pkg-1.0` schema family published at `science-model/schemas/`. Two surface-specific profiles share a common base:
  - `science-pkg-entity-1.0.json` — validates dataset entity frontmatter; forbids per-resource fields (no `resources[]`).
  - `science-pkg-runtime-1.0.json` — validates runtime `datapackage.yaml` files; requires `resources[]` (Frictionless).
  Both extend Frictionless DataPackage and share science-specific extension fields (`origin`, `tier`, `ontology_terms`, `access`, `derivation`).
- Replacement of `templates/dataset.md` with the unified schema described in Data Model below. Backward-compatible parsing of legacy flat `access: <level>` and `datasets:` field.
- `origin: external | derived` discriminator on every `dataset` entity. Mutually exclusive top-level blocks: `access:` (external) and `derivation:` (derived).
- `access:` block as designed in rev 1 (level, verified, verification_method, last_reviewed, verified_by, source_url, credentials_required, local_path, exception). The `datapackage:` field moves from `access.datapackage` to top-level.
- `derivation:` block (workflow, workflow_run, git_commit, config_snapshot, produced_at, inputs).
- `consumed_by` backlinks unified across both origins; `parent_dataset` / `siblings` lineage retained.
- Two new prose sections on dataset entities (rev 1 carry-forward): "Access verification log" (external) and "Granularity at this access level".
- Ten state invariants (rev 1's six plus four new ones for derivation symmetry, origin-block exclusion, and transitive input validation).
- `/science:plan-pipeline` Step 2b (data-access gate) and Step 4.5 (backlink write) — rev 1 carry-forward, extended to handle both origins.
- `/science:review-pipeline` Dim 3 — rev 1 carry-forward, extended to handle derivation.
- `/science:find-datasets` — rev 1 carry-forward (one entity per artefact at distinct access level for external sources only).
- New: workflow declares logical outputs in `templates/workflow.md`'s frontmatter (`outputs:` block).
- New: `templates/workflow-run.md` gains `produces:` and `inputs:` fields.
- New: `science-tool dataset register-run <workflow-run-slug>` command — emits derived dataset entities from a completed run + writes per-output `datapackage.yaml` files; idempotent.
- New: `science-tool dataset reconcile <slug>` command — checks entity ↔ runtime drift on the narrow ownership table.
- New: `science-tool data-package migrate <slug>` command — splits a legacy `data-package` entity into N derived `dataset` entities + 1 `research-package` entity; required for projects to migrate before strict graph-build mode succeeds.
- Renamed entity type: `data-package` → `research-package`. New entity location: co-located with the rendered bundle at `research/packages/<lens>/<section>/research-package.md`. First entity type to live outside `doc/`.
- `research-package` carries `displays: [dataset:<slug>, ...]` referring to the derived datasets it renders. Provenance fields (workflow_run, inputs, etc.) are removed from `research-package` (now live on the derived datasets).
- `science-tool health` grows twelve anomaly classes (rev 1's five plus seven new for derivation, asymmetric edges, broken input chains, origin/block mismatch, runtime stageability, research-package symmetry, unmigrated data-package).
- Per-entity-type discovery rule (small precursor to Spec Y's resolver): the graph builder gains a config mapping entity type → glob pattern, used for two paths in v1 (dataset under `doc/datasets/`, research-package under `research/packages/<...>/research-package.md`).
- Strict migration posture for the `data-package` → `research-package` rename: the graph builder fails with a descriptive error on any unmigrated `data-package` entity. No silent shim.

### Out of scope (v1)

- Multi-backend entity storage (datapackage-directory backend for datasets, aggregate-json backend for lightweight entities like rare topics). This is **Spec Y**, sibling to this spec, written immediately after v1 ships.
- Automated `science-tool dataset verify <slug>` (external verification automation). Documented as follow-on; v1 is structural-only.
- Automated `science-tool dataset stage <slug>` (materialize runtime `datapackage.yaml` from entity for external sources). Documented as follow-on.
- Automated `science-tool dataset migrate <slug>` (legacy flat-access → structured). Documented as follow-on.
- Automated `last_reviewed` expiry enforcement. v1 surfaces staleness; it does not block on stale reviews.
- Per-resource SHA256 / size / format extension fields on `science-pkg`'s resource block beyond what Frictionless DataResource already provides. v1's resource shape is plain Frictionless.
- Cross-project dataset-entity sharing. Each project carries its own `doc/datasets/` and `research/packages/`.
- Propagation of `consumed_by` backlinks to the RDF knowledge graph. Frontmatter-only for v1.
- A `science_resource` per-resource extension block (column-level ontology, units, validation rules). Mentioned as future work.

## Architecture Overview

Two surfaces, one schema family.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Schema family: science-pkg-1.0 (Frictionless DataPackage + extensions) │
│  Validates: entity frontmatter AND on-disk datapackage.yaml             │
└─────────────────────────────────────────────────────────────────────────┘
            ▲                                              ▲
            │                                              │
┌───────────┴──────────────────┐          ┌────────────────┴──────────────┐
│  Entity surface              │          │  Runtime surface              │
│  doc/datasets/<slug>.md      │          │  data/<slug>/datapackage.yaml │
│  YAML frontmatter            │          │  results/<wf>/<run>/          │
│  + narrative prose           │          │      datapackage.yaml         │
│                              │          │                               │
│  Project-level metadata:     │          │  Resource-level metadata:     │
│  - identity, title           │          │  - paths, hashes, sizes       │
│  - origin discriminator      │          │  - schemas (per-resource)     │
│  - access OR derivation      │          │  - formats, dialects          │
│  - ontology terms            │          │  - science-pkg extension      │
│  - consumed_by backlinks     │          │      block (mirrors entity's  │
│  - narrative log             │          │      provenance/ontology)     │
└──────────────────────────────┘          └───────────────────────────────┘
                                                        ▲
                                                        │
                                              ┌─────────┴──────────┐
                                              │  Workflow rule     │
                                              │  writes this on    │
                                              │  successful run    │
                                              └────────────────────┘
```

**Three entity types in this design:**

1. **`dataset`** (unified) — every external source AND every workflow output. Discriminated by `origin: external | derived`. Markdown-as-source in v1; promoted to a datapackage-directory backend in Spec Y.

2. **`research-package`** (renamed from `data-package`) — the narrative-rendering bundle (cells, figures, prose, vega-lite, code excerpts). No longer carries data resources; instead has a `displays:` field listing the derived `dataset` entities it renders. The web-app's "view source" page consumes these.

3. **`workflow-run`** (existing) — gains `produces:` and `inputs:` lists. `produces:` is the inverse of `dataset.derivation.workflow_run` (each derived dataset's run lists it back). `inputs:` enumerates the upstream `dataset:<slug>` entities the run consumed; symmetric with each upstream dataset's `consumed_by` list (which includes `workflow-run:<slug>`).

**Data flow:**

- **External:** `find-datasets` creates a `dataset` entity (`origin: external`, `access.verified: false`). User verifies + stages. Entity flips `access.verified: true`; a future `science-tool dataset stage` materializes `data/<slug>/datapackage.yaml` from the entity. Workflow consumes from that runtime path.
- **Derived:** Workflow rule produces output files + writes `results/<wf>/<run>/datapackage.yaml` (the run-aggregate, as today). A terminal `register_dataset_entities` rule (or `science-tool dataset register-run`) does two things: (1) emits one `dataset` entity per declared output in the workflow's `outputs:` block (each with `origin: derived` and `derivation.workflow_run` pointing back); (2) writes per-output runtime datapackages at `results/<wf>/<run>/<output-slug>/datapackage.yaml`, each containing only the resources whose `name` matches that output's `resource_names:`. The dataset entity's `datapackage:` field points at the per-output file, NOT the run-aggregate, so consumers know exactly which resources belong to them without filtering.

## The `science-pkg` Schema Family

Published as a schema family under `science-model/schemas/`, with two surface-specific profiles sharing a common base of science extensions. Differences between the surfaces are *which fields are required and which are forbidden*, not which extensions exist.

| File | Profile string | Validates | Forbids |
|---|---|---|---|
| `science-pkg-entity-1.0.json` | `science-pkg-entity-1.0` | YAML frontmatter of `dataset:<slug>` entity files | `resources[]` (per-resource info lives in runtime only) |
| `science-pkg-runtime-1.0.json` | `science-pkg-runtime-1.0` | `datapackage.yaml` files on disk (next to staged data, in `data/<slug>/` or `results/<wf>/<run>/<output>/`) | `access:` and `derivation:` blocks at top-level (these are entity-only — runtime MAY mirror them as advisory cached fields, validated by a softer schema) |

Both profiles inherit Frictionless DataPackage's required `name`, optional `title`, `description`, `licenses`, and the `resources[]` shape (when applicable). Both declare `profiles: ["science-pkg-entity-1.0"]` or `profiles: ["science-pkg-runtime-1.0"]` respectively.

### Ownership table — single source of truth per field

The boundary is narrow and machine-checkable:

| Field group | Owner | Surface |
|---|---|---|
| `id`, `type`, `title`, `status`, `tier`, `origin`, `consumed_by`, `parent_dataset`, `siblings`, `source_refs`, `related`, narrative prose | Entity | `doc/datasets/<slug>.md` (entity surface) |
| `access:` block (verification, exception, source_url, credentials, local_path) | Entity | entity surface only |
| `derivation:` block (workflow, workflow_run, git_commit, config_snapshot, produced_at, inputs) | Entity | entity surface only |
| `accessions:` (external accession IDs) | Entity | entity surface only |
| `ontology_terms:`, `license:`, `update_cadence:` | Entity (canonical) — runtime MAY mirror as advisory cached fields for shareability | both, with entity authoritative on conflict |
| `name`, `description`, `resources[]` (per-resource `name`, `path`, `format`, `mediatype`, `bytes`, `hash`, `schema`) | Runtime (canonical) — entity does NOT carry | runtime surface only |
| `datapackage:` (pointer from entity to runtime file) | Entity | entity surface only |

`science-tool dataset reconcile <slug>` checks the **only** legitimate duplication channel: the cached `ontology_terms`/`license`/`update_cadence` fields if mirrored to the runtime. Drift in this narrow set is a warning. There is no per-resource drift channel because the entity does not carry `resources[]` at all.

**Top-level science extensions (entity surface):**

| Field | Type | Required when | Notes |
|---|---|---|---|
| `profiles` | array of string | always | MUST include `"science-pkg-entity-1.0"` |
| `origin` | enum `external|derived` | always | Discriminator. Defaults to `external` for back-compat reading. |
| `tier` | enum `use-now|evaluate-next|track` | always | Discovery priority. |
| `update_cadence` | enum | optional | `static|rolling|monthly|quarterly|annual|versioned-releases`. |
| `ontology_terms` | array of CURIE | optional | Domain semantic tags. |
| `datapackage` | string (relative path) | optional | Pointer to the runtime `datapackage.yaml`. For derived datasets: the per-output runtime file (`results/<wf>/<run>/<output-slug>/datapackage.yaml`), not the run-aggregate. |
| `local_path` | string (relative path) | optional, external only | Single-file escape hatch. Mutually exclusive with `datapackage` at runtime; `datapackage` wins when both set. |
| `consumed_by` | array of `<type>:<slug>` | optional | Downstream consumers (plans, workflow-runs, research-packages). Always allowed. |
| `parent_dataset` | `dataset:<slug>` | optional | Lineage (mostly external; allowed for derived). |
| `siblings` | array of `dataset:<slug>` | optional | Cached view; regenerable from children's `parent_dataset`. |
| `access` | object | required iff `origin == external` | Verification gate state. Forbidden when derived. |
| `derivation` | object | required iff `origin == derived` | Provenance. Forbidden when external. |
| `accessions` | array of string | optional, external only | External accession IDs (renamed from `datasets:`). |

**`access:` block** (unchanged from rev 1 except `datapackage` and `local_path` move to top-level):

```yaml
access:
  level: public | registration | controlled | commercial | mixed
  verified: bool
  verification_method: retrieved | credential-confirmed | ""
  last_reviewed: YYYY-MM-DD
  verified_by: ""
  source_url: ""
  credentials_required: ""
  exception:
    mode: "" | scope-reduced | expanded-to-acquire | substituted
    decision_date: YYYY-MM-DD
    followup_task: "task:<id>"
    superseded_by_dataset: "dataset:<slug>"
    rationale: ""
```

`mixed` is retained for back-compat but discouraged for new entities; prefer granular siblings.

**`derivation:` block** (new):

```yaml
derivation:
  workflow: "workflow:<slug>"
  workflow_run: "workflow-run:<slug>"
  git_commit: ""                 # commit pinned at run time
  config_snapshot: ""            # path to frozen config used by the run
  produced_at: ""                # ISO-8601 timestamp
  inputs:                        # transitive gate dependency
    - "dataset:<slug>"
    - "dataset:<slug>"
```

Every field is required when `origin == derived`.

**Resources block** (runtime surface only — Frictionless DataResource):

The standard Frictionless `resources[]` block carries per-resource `name`, `path`, `format`, `mediatype`, `bytes`, `hash`, `schema`. **The entity surface does NOT carry `resources[]`** — per-resource information is canonical in the runtime `datapackage.yaml` at `entity.datapackage`. Entity-surface validation rejects a frontmatter `resources:` field; consumers needing resource-level info read the runtime file via `entity.datapackage`. v1 does not extend per-resource fields; the `science_resource` per-resource extension is future work.

## Data Model

### Unified `dataset` entity — example, `origin: external`

```yaml
---
id: "dataset:li2021-nature-coding-snvs"
type: "dataset"
title: "Li 2021 Nature Supplementary Table 3 — coding SNVs"
status: "active"
profiles: ["science-pkg-entity-1.0"]
origin: "external"

tier: "use-now"
license: "CC-BY-4.0"
update_cadence: "static"
ontology_terms: []

datapackage: "data/li2021-nature-coding-snvs/datapackage.yaml"
local_path: ""                                                    # alternative to datapackage; mutually exclusive at runtime
accessions:
  - "springer:41586_2021_3836_MOESM5_ESM"

access:
  level: "public"
  verified: true
  verification_method: "retrieved"
  last_reviewed: "2026-04-19"
  verified_by: "claude"
  source_url: "https://static-content.springer.com/..."
  credentials_required: ""
  exception:
    mode: ""
    decision_date: ""
    followup_task: ""
    superseded_by_dataset: ""
    rationale: ""

parent_dataset: "dataset:li2021"
siblings: []

# (No resources[] field — per-resource info lives in the runtime datapackage.yaml at entity.datapackage)

consumed_by:
  - "plan:2026-04-18-t111-normal-tissue-spectra-plan"

source_refs: ["cite:Li2021"]
related: []
created: "2026-04-18"
updated: "2026-04-19"
---
```

### Unified `dataset` entity — example, `origin: derived`

```yaml
---
id: "dataset:theme-validation-r042-per-theme-kappa"
type: "dataset"
title: "Per-theme kappa scores — theme-validation r042"
status: "active"
profiles: ["science-pkg-entity-1.0"]
origin: "derived"

tier: "use-now"
license: "internal"
update_cadence: "static"          # derived datasets are immutable per run
ontology_terms: []

datapackage: "results/theme-validation/r042/per-theme-kappa/datapackage.yaml"   # per-output, not the run-aggregate

derivation:
  workflow: "workflow:theme-validation"
  workflow_run: "workflow-run:theme-validation-r042"
  git_commit: "abc1234"
  config_snapshot: "results/theme-validation/r042/config.yaml"
  produced_at: "2026-04-19T14:32:11Z"
  inputs:
    - "dataset:claims-corpus-2026-04"
    - "dataset:theme-taxonomy-v3"

# (No resources[] field — see results/theme-validation/r042/per-theme-kappa/datapackage.yaml for per-resource detail)

consumed_by:
  - "plan:2026-04-19-theme-mat-prep-plan"
  - "research-package:theme-validation-instability-bifurcation"

related:
  - "research-package:theme-validation-instability-bifurcation"
created: "2026-04-19"
updated: "2026-04-19"
---
```

### `research-package` entity

Co-located with the rendered bundle at `research/packages/<lens>/<section>/research-package.md` (first entity type to live outside `doc/`).

```yaml
---
id: "research-package:theme-validation-instability-bifurcation"
type: "research-package"
title: "Theme validation: instability-bifurcation kappa analysis"
status: "active"

displays:
  - "dataset:theme-validation-r042-per-theme-kappa"
  - "dataset:theme-validation-r042-structural-capability"

location: "research/packages/theme/instability-bifurcation/"
manifest: "research/packages/theme/instability-bifurcation/datapackage.yaml"

cells: "research/packages/theme/instability-bifurcation/cells.json"
figures:
  - { name: "kappa-by-theme", path: "figures/kappa-by-theme.png", caption: "..." }
vegalite_specs:
  - { name: "theme-overlap", path: "figures/theme-overlap.vl.json", caption: "..." }
code_excerpts:
  - { name: "kappa-computation", path: "excerpts/per-theme-kappa.ts", source: "scripts/per-theme-kappa.ts", lines: "12-48", github_permalink: "..." }

related: ["workflow-run:theme-validation-r042"]
created: "2026-04-19"
updated: "2026-04-19"
---
```

The narrative manifest at `research/packages/.../datapackage.yaml` enumerates only narrative resources (cells.json, figures, vega-lite specs, prose markdown, code excerpts). Data resources moved out and now live on the derived `dataset` entities the research-package displays.

### `workflow-run` additions

Two new fields on `templates/workflow-run.md`:

```yaml
produces:
  - "dataset:theme-validation-r042-per-theme-kappa"
  - "dataset:theme-validation-r042-structural-capability"

inputs:
  - "dataset:claims-corpus-2026-04"
  - "dataset:theme-taxonomy-v3"
```

`produces:` is the inverse of `dataset.derivation.workflow_run` and is required for symmetric-edge enforcement (state invariant #9). `inputs:` enumerates upstream datasets consumed by the run; populated by `register-run` from the workflow's actual runtime inputs.

`register-run` ALSO appends `workflow-run:<slug>` to each upstream dataset's `consumed_by` list (deduplicated). This makes derived consumers visible to the same `science-tool dataset consumers <slug>` reverse-lookup that surfaces plan consumers, and gives `dataset_consumed_but_unverified` health checks the same coverage for runs as for plans.

### `workflow` additions — `outputs:` block

Workflows declare their logical outputs once, in their entity frontmatter. This is what `register-run` reads to determine how to group resources into derived datasets:

```yaml
outputs:
  - slug: "per-theme-kappa"
    title: "Per-theme kappa scores"
    resource_names: ["per-theme-kappa"]    # matches Frictionless resources[].name in the run datapackage
    ontology_terms: []
  - slug: "structural-capability"
    title: "Structural capability table"
    resource_names: ["structural-capability"]
    ontology_terms: []
```

Each declared output produces one derived `dataset` entity per workflow-run **and** one per-output `datapackage.yaml` at `results/<wf>/<run>/<output-slug>/datapackage.yaml`. The dataset's slug is `<workflow-slug>-<run-slug>-<output-slug>`. The dataset's `datapackage:` field points at the per-output runtime file (NOT the run-aggregate). The per-output datapackage's `resources[]` is the subset of the run-aggregate's resources whose `name` matches the declared `resource_names:` list. Match by Frictionless `resource.name` (the stable identifier), not by `path` (which carries filesystem detail).

## State Invariants

The schema implies eleven machine-checkable rules. `science-tool health` surfaces violations as anomalies (severity per the table in the Health Check Additions section):

1. **Umbrella entities are not consumable.** An entity with a non-empty `siblings:` list (umbrella) MUST NOT appear in any other entity's `consumed_by` list. Plans consume granular siblings, never umbrellas. (Carry forward.)
2. **`verified: true` requires method + date.** `access.verified: true` implies `access.verification_method ∈ {"retrieved", "credential-confirmed"}` and `access.last_reviewed` is a non-empty YYYY-MM-DD string. (Carry forward.)
3. **`verified: true` and `exception.mode` are mutually exclusive.** A verified entity has no exception; an exception only applies to entities that are genuinely unverified but still consumable under a structured Branch-B decision. (Carry forward.)
4. **`consumed_by` entries are deduplicated** by the full `<type>:<slug>` key. Duplicate writes are no-ops. (Carry forward.)
5. **Children must agree with parent on lineage.** If entity A has `parent_dataset: B`, then either entity B has A in its `siblings:` list OR entity B has an empty `siblings:` list (cached-view-unmaterialized case). B's `siblings:` listing A without A's `parent_dataset: B` is a violation. (Carry forward.)
6. **`local_path` and `datapackage` precedence.** Both fields may be populated (`local_path` as a staged single-file escape hatch, `datapackage` as the structured manifest); when both are present `datapackage` wins at runtime. When neither is present on a `verified: true` external entity, it is "verified-but-not-staged" — legal, but any plan must stage before execution. (Carry forward.)
7. **Origin/access-block exclusion.** `origin: external ⟹ access` block required, `derivation` block forbidden, `accessions` allowed. (NEW.)
8. **Origin/derivation-block exclusion.** `origin: derived ⟹ derivation` block required, `access` block forbidden, `accessions` forbidden. (NEW.)
9. **Symmetric workflow-run edge.** A derived dataset's `derivation.workflow_run` MUST exist as an entity, and that workflow-run's `produces:` list MUST include this dataset's ID. Violation: missing entity, or dataset not in `produces:`. (NEW.)
10. **Transitive input gate.** A derived dataset's `derivation.inputs` MUST all transitively pass the gate rule: each input is either external-and-(`verified: true` OR `exception.mode != ""`), or derived-and-its-own-`derivation.inputs`-pass. Cycles are forbidden. (NEW.)
11. **Symmetric research-package edge.** When a `research-package` lists `dataset:<slug>` in its `displays:` field, that dataset's `consumed_by` MUST include `research-package:<id>`. Conversely, every `research-package:<id>` appearing in a dataset's `consumed_by` MUST list that dataset in its `displays:`. Mirrors invariant #9 for workflow-runs. (NEW.)

## Lifecycle

### External — discovery → verification → planning → consumption → review

```
Discovery          /science:find-datasets creates doc/datasets/<slug>.md with:
                     origin: external
                     access.verified: false
                     access.verification_method: ""
                     access.level: <best-guess>
                     consumed_by: []
    ↓
Verification       Manually (log entry) or via future `science-tool dataset verify`:
                     Public:     retrieve source_url → confirm match →
                                 access.verified: true, verification_method: "retrieved"
                     Controlled: confirm DAR/DUA →
                                 access.verified: true, verification_method: "credential-confirmed"
    ↓
Staging            Optional: `science-tool dataset stage` materializes
                     data/<slug>/datapackage.yaml from the entity. Entity's
                     `datapackage:` field points at it. Workflows consume from
                     this runtime path, never from access.source_url.
    ↓
Planning           /science:plan-pipeline §Step 2b (gate check):
                     resolve each input to dataset:<slug>
                     enforce access.verified: true OR access.exception.mode != ""
                     halt with Branch A/B options if neither
    ↓
Plan written       /science:plan-pipeline §Step 4 writes the plan file.
                     plan:<plan-file-stem> identity is now stable.
    ↓
Backlink           /science:plan-pipeline §Step 4.5:
                     append plan:<plan-file-stem> to consumed_by on each
                     dataset the plan references.
    ↓
Execution          Pipeline reads from the runtime datapackage.yaml at the
                     entity's `datapackage:` path.
    ↓
Review             /science:review-pipeline Dim 3 verifies gate state, backlinks,
                     invariants, freshness.
```

### Parallel runs of the same workflow

Repeated invocations of the same workflow produce **parallel** derived dataset entities — one per `(workflow, run, output-slug)` tuple. Both `dataset:wf-r1-out` and `dataset:wf-r2-out` exist as `status: "active"` entities side-by-side; neither automatically supersedes the other. Each carries its own `consumed_by` independently, so a downstream plan that referenced the older run's output continues to resolve. Supersession is a manual user action (a future `science-tool dataset supersede <slug>` follow-on may automate it). v1's invariant: a derived dataset's identity is permanent; the workflow-run that produced it never changes; `consumed_by` grows monotonically.

The per-output runtime datapackage at `results/<wf>/<r1>/<output>/datapackage.yaml` is a **view** into the run-aggregate's resources at `results/<wf>/<r1>/`. Resource paths inside the per-output datapackage are kept relative to the run-aggregate root (the per-output datapackage sets `basepath: ".."`), so files stay where the workflow wrote them and the per-output datapackage acts as a slice/manifest, not a relocation. This avoids file-moves at registration time and keeps the workflow's existing on-disk layout intact.

### Derived — workflow run → registration → planning downstream

```
Workflow run       Snakemake rule produces output files; writes the run-aggregate
                     results/<wf>/<run>/datapackage.yaml as it does today.
    ↓
Registration       Terminal `register_dataset_entities` rule invokes:
                     science-tool dataset register-run workflow-run:<slug>
                   This reads the workflow's `outputs:` block and the run-aggregate
                   datapackage.yaml, then for each declared output:
                     1. Writes a per-output datapackage at
                        results/<wf>/<run>/<output-slug>/datapackage.yaml
                        containing only the resources whose `name` is in the
                        output's `resource_names:` list. (Resource paths inside
                        are relative to the output directory.)
                     2. Emits one derived dataset entity at
                        doc/datasets/<wf>-<run>-<output-slug>.md with:
                          origin: derived
                          derivation.workflow_run: workflow-run:<slug>
                          derivation.workflow: workflow:<slug>
                          derivation.git_commit: <commit>
                          derivation.config_snapshot: <path>
                          derivation.produced_at: <timestamp>
                          derivation.inputs: <runtime-resolved upstream datasets>
                          datapackage: results/<wf>/<run>/<output-slug>/datapackage.yaml
                          (no resources[] — runtime is canonical)
                   Symmetric edges written:
                     - workflow-run.produces gains the dataset slug (invariant #9).
                     - Each upstream input dataset's consumed_by gains
                       workflow-run:<slug> (matches the `consumers` reverse-lookup).
                   Idempotent: re-runs no-op when nothing changed; warn + report drift
                   when the run's resources have shifted.
    ↓
Planning downstream /science:plan-pipeline §Step 2b for plans consuming this
                     dataset:
                     enforce derivation.workflow_run exists +
                             produces: edge symmetric +
                             derivation.inputs transitively pass
                     halt if any rule violated
    ↓
Backlink           Step 4.5 appends plan:<stem> to consumed_by — identical
                     mechanism as external.
    ↓
Execution          Downstream pipeline reads from the per-output datapackage.yaml
                     at the entity's `datapackage:` path. No filtering needed —
                     every resource in the file belongs to this dataset.
    ↓
Review             Dim 3 verifies symmetric edges, transitive input chain,
                     `consumed_by` backlinks, runtime stageability, drift state.
```

### Task-mode example (carry forward from rev 1, extended)

`/science:plan-pipeline` in Task mode for cbioportal's t111:

1. **Input:** task ID `t111`.
2. **Step 2 (identify computational requirements):** the planner enumerates inputs: Li 2021 normal-tissue mutation calls (external); a UBERON mapping table (external); per-theme normalized counts (derived, from a prior workflow run).
3. **Step 2b (gate check):**
   - `dataset:li2021-nature-coding-snvs` — `origin: external`, `access.verified: true` → PASS.
   - `dataset:uberon-snapshot-2026-04-01` — `origin: external`, `access.verified: true` → PASS.
   - `dataset:theme-validation-r042-per-theme-counts` — `origin: derived`. Check (a) `derivation.workflow_run: workflow-run:theme-validation-r042` exists; (b) that run's `produces:` includes this dataset; (c) `derivation.inputs` transitively pass. PASS.
   - `dataset:xu2025-ega-wes-somatic-calls` — `origin: external`, `access.verified: false`, no `exception.mode`. HALT with Branch A/B options.
   - User selects Branch B (a) (scope-reduce). Planner writes `access.exception` and a verification log entry. Re-runs gate; passes.
4. **Step 4 (write plan):** file written at `doc/plans/2026-04-18-t111-normal-tissue-spectra-plan.md`. Identity is `plan:2026-04-18-t111-normal-tissue-spectra-plan`.
5. **Step 4.5 (backlink write):** `plan:<stem>` appended to `consumed_by` on each of the four referenced datasets (regardless of origin).
6. **Step 5 (inquiry-status update):** skipped in Task mode.

## Command Integrations

### `/science:find-datasets`

Unchanged from rev 1. Only emits `origin: external` entities. New entities start with `origin: external`, `access.verified: false`, `last_reviewed: ""`, `consumed_by: []`. Discovery-time `access.level`, `access.source_url`, `access.credentials_required` populated from evidence. When uncertain, use the most restrictive known level.

### `/science:plan-pipeline` — Step 2b (data-access gate, both origins)

```markdown
### Step 2b: Data-access gate (both modes)

For each input data source identified in Step 2:

1. Resolve to a `dataset:<slug>` entity. If no entity exists:
   - For external sources: invoke `/science:find-datasets`. Do not proceed
     with a URL alone.
   - For derived sources: halt with "no dataset entity found for
     <slug>; ensure the producing workflow has an `outputs:` block and
     run `science-tool dataset register-run <run-slug>`."
2. Check the gate per origin:
   - `origin: external`:
     - PASS if `access.verified: true`.
     - PASS if `access.verified: false` AND `access.exception.mode != ""`.
     - HALT otherwise with Branch A/B options (per rev 1).
   - `origin: derived`:
     - Check `derivation.workflow_run` resolves to an entity. HALT if not.
     - Check that workflow-run's `produces:` includes this dataset's ID.
       HALT if asymmetric.
     - Recursively check each ID in `derivation.inputs` passes the gate.
       HALT with the broken-link path if any input transitively fails.
       Cycle detection: maintain a visited-set; HALT on revisit.
3. Do NOT mutate `consumed_by` here. Backlink write is Step 4.5.
```

### `/science:plan-pipeline` — Step 4.5 (backlink write, both origins)

Unchanged from rev 1. Works identically for both origins. Computes `plan:<plan-file-stem>` from the written plan filename. For each dataset referenced in Step 2b, appends `plan:<stem>` to `consumed_by` (deduplicated). Appends a short prose log entry to each dataset's verification log.

### `/science:review-pipeline` — Dim 3 (Data Availability)

```markdown
#### Dimension 3: Data Availability

For each input data source (every `BoundaryIn` node or data-acquisition step
in the plan):

- Does it resolve to a `dataset:<slug>` entity?
- Per origin (verification gate):
  - `external`: `access.verified: true` OR `access.exception.mode != ""`.
    `access.source_url` populated when verified.
    `access.last_reviewed` within the last 12 months.
  - `derived`: `derivation.workflow_run` exists; symmetric `produces:` edge
    present; `derivation.inputs` transitively pass.
- Runtime stageability (separate gate, runs in addition to verification):
  - At least one of `entity.datapackage` or `entity.local_path` is populated
    AND the referenced runtime file exists on disk.
  - Reason: review-pipeline runs when execution is imminent. A
    verified-but-unstaged dataset is plannable but not executable; this gate
    catches the gap.
- `consumed_by` includes `plan:<this-plan-file-stem>`.
- All eleven state invariants hold for the entity.

Scoring:

- PASS — all sources resolve; verification gate satisfied per origin;
  runtime stageability satisfied; backlink present; freshness OK; invariants hold.
- WARN — stale `last_reviewed` (> 12 months); missing canonical
  `plan:<stem>` backlink; cached-field drift between entity and runtime
  (`ontology_terms`/`license`/`update_cadence` only — no per-resource
  drift channel exists); lineage drift.
- FAIL — any of:
  - A source does not resolve to a dataset entity.
  - External `access.verified: false` with `access.exception.mode: ""`.
  - External `access.verified: true` but `verification_method: ""` or no
    `last_reviewed`.
  - Derived missing `workflow_run` entity, asymmetric `produces:` edge, or
    broken transitive input chain.
  - **Runtime stageability fails: neither `datapackage` nor `local_path`
    populated, OR the referenced runtime file does not exist on disk.**
  - A plan references an umbrella entity (non-empty `siblings:`).
  - Origin/block-exclusion violation (#7 or #8).
  - research-package symmetry violation (#11).
```

## CLI Affordances

New `science-tool dataset` subcommands; v1 ships read-only commands plus the two write-side commands needed for the workflow integration (`register-run`, `reconcile`).

**v1 read-only:**

```bash
science-tool dataset list                              # all entities
science-tool dataset list --origin external|derived    # NEW filter
science-tool dataset list --unverified                 # external, access.verified: false
science-tool dataset list --stale-review --months 12
science-tool dataset list --level controlled
science-tool dataset consumers <slug>                  # reverse lookup via consumed_by
science-tool dataset show <slug>                       # full entity view
```

**v1 write-side:**

```bash
science-tool dataset register-run <workflow-run-slug>  # emit derived entities + per-output datapackages
science-tool dataset reconcile <slug>                  # entity ↔ runtime cached-field drift check
science-tool data-package migrate <slug>               # split legacy data-package → derived datasets + research-package
```

`register-run` is idempotent: re-running on an already-registered run no-ops if outputs match the current state, or warns + reports drift if the run's resources have shifted. Writes:
- N per-output datapackages at `results/<wf>/<run>/<output-slug>/datapackage.yaml`.
- N derived dataset entities at `doc/datasets/<wf>-<run>-<output-slug>.md`.
- Symmetric edges: `workflow-run.produces`, upstream `dataset.consumed_by` (with `workflow-run:<slug>` entries).

`reconcile` exits non-zero only on cached-field drift in the narrow set: `ontology_terms`, `license`, `update_cadence` (the only fields legitimately mirrored between entity and runtime). Per-resource drift is not possible because the entity does not carry `resources[]`.

`data-package migrate` reads `doc/data-packages/<slug>.md` plus its linked `datapackage.json`, requires the source workflow to have an `outputs:` block (else fails with a pointer to add one), then emits N derived datasets + 1 research-package, and marks the old data-package with `status: superseded`. Required for projects to migrate before strict graph-build mode succeeds. Idempotent.

**Follow-on (deferred):**

```bash
science-tool dataset verify <slug>                     # external verification automation
science-tool dataset stage <slug>                      # materialize runtime datapackage from external entity
science-tool dataset migrate <slug>                    # legacy flat-access → structured
```

## Health Check Additions

`science-tool health` grows twelve anomaly classes (rev 1's five plus seven new):

| Anomaly | Severity | Trigger |
|---|---|---|
| `dataset_consumed_but_unverified` | error | external entity has non-empty `consumed_by` but `access.verified: false` AND `access.exception.mode: ""` |
| `dataset_stale_review` | warning | external entity has `access.verified: true` but `last_reviewed` older than 12 months |
| `dataset_missing_source_url` | warning | external entity has `access.verified: true` but `access.source_url: ""` |
| `dataset_cached_field_drift` | warning | entity's `ontology_terms`, `license`, or `update_cadence` differs from the runtime `datapackage.yaml` at `entity.datapackage` (the only legitimate duplication channel; per-resource drift is impossible because the entity doesn't carry `resources[]`) |
| `dataset_invariant_violation` | warning | any of invariants #1, #2, #3, #4, #5, #6 false |
| `dataset_derived_missing_workflow_run` | error | derived entity's `derivation.workflow_run` doesn't resolve to a `workflow-run` entity |
| `dataset_derived_asymmetric_edge` | error | derived entity's `workflow-run` exists but doesn't list this dataset's ID in `produces:` |
| `dataset_derived_input_chain_broken` | error | derived entity's `derivation.inputs` transitively fails the gate (cycle, missing entity, or unverified leaf); error names the breaking link |
| `dataset_origin_block_mismatch` | error | invariant #7 or #8 violated (e.g., `access:` on derived; `derivation:` on external; `accessions:` on derived) |
| `dataset_verified_but_unstageable` | warning | external entity has `access.verified: true` (or non-empty exception) but neither `datapackage:` nor `local_path:` is populated, OR the file each points at doesn't exist on disk. Plannable but not executable; `review-pipeline` Dim 3 escalates to FAIL |
| `dataset_research_package_asymmetric` | error | invariant #11 violated: `research-package.displays` lists a dataset whose `consumed_by` doesn't include this research-package, OR a dataset's `consumed_by` lists a research-package whose `displays:` doesn't include the dataset |
| `data_package_unmigrated` | error | a `data-package` entity exists in `doc/data-packages/` without `status: superseded`. Strict mode: graph build fails until `science-tool data-package migrate <slug>` is run |

## Template Updates

- **`templates/dataset.md`** — replaced. Defaults to `origin: external` for back-compat reading. Contains both `access:` and `derivation:` blocks in the template comments with notes on which to populate.
- **`templates/workflow.md`** — gains an `outputs:` block.
- **`templates/workflow-run.md`** — gains `produces:` and `inputs:` lists.
- **`templates/data-package.md`** — renamed to `templates/research-package.md`. `provenance:` block removed (lives on derived datasets). `displays:` field added. Data-resource fields removed.

The graph builder's per-entity-type discovery rule:

```yaml
# config / convention (v1: hardcoded; Spec Y: pluggable)
entity_discovery:
  default: "doc/**/*.md"
  dataset: "doc/datasets/**/*.md"
  research-package: "research/packages/**/research-package.md"
```

## Migration

Two postures, depending on which migration path:

- **Path 1 (legacy `dataset.md` → unified `dataset`):** Opt-in, additive, lazy. Existing files continue to parse via back-compat read rules. Migration is per-entity, triggered when a plan next touches the entity.
- **Path 2 (legacy `data-package` → split into derived `dataset` + `research-package`):** **Strict, eager.** The graph builder fails on any unmigrated `data-package` entity. v1 ships `science-tool data-package migrate <slug>` to make this enforceable rather than blocking. Projects with existing data-packages MUST migrate them as a one-time pre-flight before the graph build will succeed under v1. The trade-off — upfront effort for sharply reduced code complexity — was an explicit design decision; few projects are affected.

### Path 1 — Legacy `dataset.md` → unified `dataset` (rev 1 carry-forward)

- Flat `access: public|controlled|mixed` parses as `access.level: <value>` with all other subfields defaulting (`verified: false`, etc.). Origin defaults to `external` when not specified.
- `datasets: [...]` aliases to `accessions: [...]`.
- `science-tool dataset migrate <slug>` (deferred) automates rewrite.

Net: legacy externals continue to function; gate halts until verified or exception added.

### Path 2 — Existing `data-package` entity → split into derived `dataset` + `research-package`

`science-tool data-package migrate <slug>` is shipped in v1:

1. Reads `doc/data-packages/<slug>.md` and the linked `datapackage.json`.
2. Reads the source workflow's `outputs:` block. **If absent, fails fast** with the message: `workflow:<slug> has no outputs[] block; add one (see Path 3) before migrating data-package:<slug>`. No silent fallback — granularity intent matters.
3. For each declared output:
   - Writes a per-output `datapackage.yaml` at `results/<wf>/<run>/<output-slug>/datapackage.yaml` containing only the resources whose Frictionless `name` is in `output.resource_names`.
   - Emits one derived `dataset` entity at `doc/datasets/<wf>-<run>-<output-slug>.md`, with `origin: derived`, `derivation:` populated from the data-package's existing `provenance` block, and `datapackage:` pointing at the per-output runtime file.
4. Emits one `research-package` entity at `research/packages/<lens>/<section>/research-package.md` with `displays:` listing the N derived datasets and the existing narrative bundle (`cells.json`, `figures`, `vegalite_specs`, `code_excerpts`) preserved.
5. Writes symmetric edges: `workflow-run.produces` (each new derived dataset's slug); each new dataset's `consumed_by` (the research-package's id, satisfying invariant #11); each upstream input dataset's `consumed_by` (the workflow-run's id).
6. Marks the old `doc/data-packages/<slug>.md` with `status: superseded` and `superseded_by: research-package:<slug>`. Old file kept for git history.

Idempotent: re-running on an already-migrated source no-ops with a one-line summary.

**Strict graph-build mode:** the graph builder fails on any `data-package` entity in `doc/data-packages/` without `status: superseded`. Error: `unmigrated data-package entity '<slug>'; run 'science-tool data-package migrate <slug>' to split into derived dataset(s) + research-package`. Names every offending slug. Projects with no `data-package` entries (most pre-2026-03-30 projects) see no change.

### Path 3 — Existing `workflow.md` → add `outputs:` block

Workflows currently have no `outputs:` declaration. Adding one is opt-in.

- Workflows without `outputs:` continue to run; their runs don't auto-register derived datasets.
- Plans that try to consume those runs' outputs halt at the gate until the workflow gains `outputs:` AND its terminal `register_dataset_entities` rule runs.

A `science-tool workflow add-outputs <slug>` helper (deferred) walks an existing workflow's most recent `datapackage.json` and offers an interactive grouping into logical outputs.

### Path 4 — Existing `workflow-run.md` → gains `produces:` and `inputs:`

Pure additive. Old workflow-run entities continue to parse with empty implicit lists. The `register-run` command populates `produces:`/`inputs:` for new runs. Historical runs may be left unmigrated unless a downstream plan needs to query them.

### Recommended migration sequence

1. **Day 0** (this spec lands):
   - Projects with no `data-package` entities: no immediate action; legacy `dataset.md` entries continue to parse. Gate halts fire lazily when a new plan touches an unmigrated entity.
   - Projects with existing `data-package` entities: graph build fails until each is migrated. **One-time pre-flight required:**
     a. `science-tool data-package list` (read-only) — enumerates unmigrated entries.
     b. For each source workflow: ensure `templates/workflow.md` has an `outputs:` block (Path 3). Adding the block is opt-in but a prerequisite for `data-package migrate`.
     c. `science-tool data-package migrate <slug>` for each entry. Idempotent; safe to re-run.
2. **As needed**: when a new plan touches a legacy external dataset, the gate halts → user migrates that one entity (verify or add exception).
3. **As needed**: when a workflow gets a new `outputs:` block + the terminal `register_dataset_entities` rule, future runs auto-emit derived dataset entities.

**No data file movement.** Migration touches `doc/`, `research/packages/`, `templates/` only. Runtime `datapackage.yaml` files stay in place; new derived dataset entities point at them.

## Testing

### Unit tests

`science-tool/tests/test_science_pkg_schema.py`:
- Two profiles validated separately: `science-pkg-entity-1.0` and `science-pkg-runtime-1.0`.
- All eleven invariants tested with synthetic frontmatter triggering each violation.
- `origin: external` and `origin: derived` shapes parse; missing `origin:` defaults to `external`.
- Per-origin block requirement (#7, #8): `derivation:` on external rejects, `access:` on derived rejects.
- Entity profile rejects a top-level `resources:` field (single-source-of-truth invariant).
- Runtime profile validates Frictionless `resources[]` and rejects entity-only blocks (`access:`, `derivation:`) at top level (advisory mirror is in a softer schema, not the runtime profile).

`science-tool/tests/test_dataset_entity.py`:
- Legacy flat `access: public` parses to `access.level: public, verified: false`.
- Legacy `datasets:` aliases to `accessions:`.
- New `derivation:` block parses with all fields.
- Schema validation produces same errors at parse time as raw schema test.

`science-tool/tests/test_health_dataset.py`:
- Each of the twelve anomaly classes fires for its trigger; doesn't fire when absent.
- Transitive `dataset_derived_input_chain_broken` walks the chain and reports the breaking link by name.
- `dataset_verified_but_unstageable` fires when external entity is verified but lacks both `datapackage:` and `local_path:` (or the referenced file is missing).
- `dataset_research_package_asymmetric` fires in both directions of invariant #11 violation.
- `data_package_unmigrated` fires for any non-superseded entity in `doc/data-packages/`.

`science-tool/tests/test_dataset_cli.py`:
- `dataset list --origin external|derived` filters correctly.
- `dataset register-run <run>` emits N entities AND N per-output `datapackage.yaml` files matching the workflow's `outputs[].resource_names`; idempotent (re-run produces no diff). Symmetric edges written: `workflow-run.produces`, upstream `dataset.consumed_by`.
- `dataset reconcile <slug>` exits non-zero ONLY on cached-field drift (`ontology_terms`, `license`, `update_cadence`); never reports per-resource drift (entity has no `resources[]`).
- `dataset consumers <slug>` returns `consumed_by` list; works for both origins; includes plans, workflow-runs, and research-packages.
- `data-package migrate <slug>` fails with a clear error when the source workflow has no `outputs:` block.
- `data-package migrate <slug>` is idempotent; rerun no-ops with a one-line summary.

`science-tool/tests/test_data_package_migration.py`:
- `data-package migrate <slug>` produces N derived datasets + 1 research-package matching the workflow's `outputs:` declaration AND N per-output `datapackage.yaml` files.
- Per-output datapackage's `resources[]` are exactly the resources whose `name` is in `output.resource_names`.
- Symmetric edges written: each new dataset's `consumed_by` includes the research-package; research-package's `displays:` lists every new dataset (invariant #11).
- Old `data-package` file gets `status: superseded` and `superseded_by:` populated; not deleted.
- Strict mode: graph build fails with descriptive error when any non-superseded `data-package` entity is found; error names every offending slug and points at the migrate command.

### Integration tests

`science-tool/tests/test_plan_pipeline_data_gate.py` (extends rev 1):
- Plan against verified external input: passes Step 2b, Step 4.5 appends backlink.
- Plan against derived input pointing at registered run: passes.
- Plan against derived input whose `derivation.workflow_run` doesn't exist: halts.
- Plan against derived input with asymmetric `produces:` edge: halts with invariant violation.
- Plan against derived input whose chain contains an unverified external: halts with broken-link path printed.

`science-tool/tests/test_review_pipeline_dim3.py`:
- Mixed-origin pipeline: PASS when each branch's gate is satisfied; FAILs surface per item.
- WARN tier triggers (stale `last_reviewed`, missing backlink, cached-field drift).
- Runtime stageability FAIL: a verified external dataset with neither `datapackage:` nor `local_path:` set, or with the referenced file missing on disk.
- research-package symmetry FAIL: invariant #11 violation in either direction.

`science-tool/tests/test_workflow_registration.py`:
- End-to-end with toy workflow + `outputs:` declaration: terminal `register_dataset_entities` rule emits derived dataset entities AND per-output `datapackage.yaml` files; gate accepts a downstream plan reading from the per-output file; asymmetric edges and missing entities both detected.
- Per-output datapackage's resource paths are relative to the per-output directory; consumer can read it without filesystem-relative path arithmetic.

`science-tool/tests/test_research_package_split.py`:
- Round-trip a fixture data-package → migrate → verify research-package's `displays:` references valid derived datasets → verify rendering bundle (`cells.json`, figures, vega-lite specs) unchanged.
- research-package entity at `research/packages/<lens>/<section>/research-package.md` is discovered by graph builder.

`science-tool/tests/test_graph_build_paths.py`:
- Graph builder scans `doc/datasets/**/*.md` and `research/packages/**/research-package.md` per the discovery rule. (First entity type outside `doc/`.)
- Graph builder fails with descriptive error on any unmigrated `data-package` entity.

### Test fixtures

`science-tool/tests/fixtures/datasets/`:
- `external_verified_public.md`
- `external_unverified_with_exception.md`
- `external_legacy_flat_access.md` (back-compat)
- `derived_simple.md`
- `derived_with_chain.md` (transitive inputs)
- `data_package_pre_migration.md` + linked `datapackage.json` (for migration test)
- Matching `workflow.md` with `outputs:` block
- Matching `workflow-run.md` with `produces:`/`inputs:`

## Relationship to Existing Specs

- **Rev 1 of this spec** — superseded; this is rev 2. v1 content (access verification gate, structured exception, granularity, consumed_by, plan-pipeline Step 2b/4.5) is preserved and extended to cover derived data.
- **2026-03-30 research-provenance-upstream spec** — the `data-package` entity it introduced is renamed and split. The narrative-rendering bundle, cells.json, figures, vega-lite, code excerpts, prose markdown all carry forward unchanged in shape; they now live under a `research-package` entity. The data half folds into derived `dataset` entities.
- **`commands/find-datasets.md`** — amended (one entity per artefact at distinct external access level; default `verified: false`).
- **`commands/plan-pipeline.md`** — adds Step 2b and Step 4.5 (rev 1 carry-forward, extended for derived).
- **`commands/review-pipeline.md`** — Dim 3 rewritten (rev 1 carry-forward, extended for derived).
- **`commands/health.md`** / `science-tool health` — adds seven anomaly classes beyond rev 1.
- **2026-04-19 entity-aspects spec** — orthogonal. Dataset entities may eventually carry `aspects:`; v1 does not address.
- **Spec Y (multi-backend entity resolver, sibling)** — this spec commits only to markdown-as-source for the entity surface. Spec Y will introduce the resolver and other backends. The science-pkg schema is the same regardless of backend; datasets are a candidate to promote to a datapackage-directory backend (where `data/<slug>/datapackage.yaml` IS the entity, no markdown sidecar needed) once Spec Y lands.

## Resolved Decisions

- **Unification.** External and workflow-derived data share a single schema family (`science-pkg`) and a single entity type (`dataset`), discriminated by `origin: external | derived`. Different origins carry different top-level blocks (`access:` vs `derivation:`) but otherwise share all other fields.
- **Schema family.** Frictionless DataPackage profile + science extensions, published once as `science-pkg-1.0` JSON Schema. Validates both entity frontmatter and runtime `datapackage.yaml`.
- **Entity surface vs runtime surface.** Entity = project-level metadata + narrative; runtime = resource-level metadata. Same schema family, different physical files, drift detected by `dataset reconcile`.
- **`data-package` → `research-package` rename.** The narrative-rendering bundle is its own entity that `displays:` derived datasets. The data half moves out of `data-package` and into derived `dataset` entities.
- **research-package entity location.** Co-located with its rendered bundle at `research/packages/<lens>/<section>/research-package.md`. First entity type to live outside `doc/`. Deferring to a universal "all entities under `doc/`" rule was rejected as artificial.
- **Per-entity-type discovery rule.** Graph builder reads a small config mapping entity type → glob pattern. Hardcoded for v1's two non-default paths; generalized in Spec Y.
- **Granularity for derived data.** One entity per logical output of a workflow run, declared explicitly via the workflow's `outputs:` block. Per-resource auto-grouping is rejected — granularity intent matters.
- **Workflow integration shape.** A terminal `register_dataset_entities` Snakemake rule per workflow invokes `science-tool dataset register-run`. Acceptable per-workflow overhead; matches existing project conventions for "package data" rules.
- **Strict migration for the `data-package` rename, with migrator shipped in v1.** Graph builder fails on unmigrated entities; `science-tool data-package migrate <slug>` is shipped in v1 (not deferred) so the strict mode is actionable. Few projects affected; trades upfront effort for reduced code complexity. No silent shim.
- **Single canonical surface for `resources[]`: runtime only.** The dataset entity does not carry `resources[]`. Per-resource information lives only in the runtime `datapackage.yaml` at `entity.datapackage`. Two surface-specific JSON Schema profiles enforce this — the entity profile rejects `resources[]`. Eliminates an entire drift channel; reduces `reconcile` to checking only the narrow set of legitimately-mirrored cached fields (`ontology_terms`, `license`, `update_cadence`).
- **Per-output runtime datapackages alongside the run-aggregate.** `register-run` writes one `datapackage.yaml` per declared output (under `results/<wf>/<run>/<output-slug>/`) AND keeps the run-aggregate at `results/<wf>/<run>/datapackage.yaml`. Each derived dataset's `datapackage:` field points at its per-output file, so consumers don't have to filter resources by name. The aggregate remains for human inspection and debugging.
- **Plan gate vs runtime stageability gate.** Step 2b (plan-pipeline) is a verification gate only — it permits exploratory planning against verified-but-not-yet-staged datasets. Dim 3 (review-pipeline) escalates an additional runtime stageability check to FAIL when an executable input lacks both `datapackage:` and `local_path:` (or the referenced file doesn't exist). Closes the "plannable but not executable" gap.
- **`outputs[].resource_names` (not `resources`).** Workflows declare logical-output groupings by Frictionless `resource.name`, the stable identifier — not by file path. The renamed field makes the matching key explicit and resilient to path renames.
- **Symmetric research-package backlinks.** Invariant #11 enforces `research-package.displays` ⟺ `dataset.consumed_by` symmetry, paralleling the workflow-run/dataset symmetry of #9. `register-run` and `data-package migrate` both write the symmetric edges; health flags drift.
- **`origin: external` default for back-compat reading.** Pre-rev-2 `dataset.md` entries continue to parse as `origin: external`.
- **No symlinks.** The runtime `datapackage.yaml` is a real file written by the workflow (derived) or materialized by `dataset stage` (external). Symlinks were rejected because the runtime file may evolve independently (per-resource hashes after staging, schemas inferred from data) and because diff/git ergonomics suffer.
- **Forward-compatibility with Spec Y.** This spec's schema is identical regardless of storage backend. Spec Y can later promote datasets to a datapackage-directory backend without changing the science-pkg schema.

## Follow-on Work

- **`science-tool dataset verify <slug>`.** Automates the external verification flip for public URLs (retrieve → SHA256 → flip `verified: true` with `verification_method: "retrieved"` → append log). Interactive prompt for controlled sources (records `credential-confirmed`).
- **`science-tool dataset stage <slug>`.** Materializes the runtime `datapackage.yaml` from the entity for external sources at staging time.
- **`science-tool dataset migrate <slug>`.** Rewrites legacy flat `access: <level>` and `datasets: [...]` fields into the structured schema.
- **`science-tool workflow add-outputs <slug>`.** Interactive helper for adding the `outputs:` block to legacy workflows. Walks the workflow's most recent `datapackage.json` and offers an interactive grouping into logical outputs.
- **`science-tool dataset reconcile --all`.** Project-wide drift scan; prints a table.
- **`last_reviewed` expiry enforcement.** If stale-review warnings go unactioned, consider upgrading to errors with a configurable threshold.
- **Shared cross-project dataset catalogue.** When multiple projects reference the same Li 2021 supplementary table, duplicating the entity is wasteful. A framework-level shared catalogue could let projects layer project-specific `consumed_by` onto a canonical entity. Non-trivial; defer.
- **`science_resource` per-resource extension.** Column-level ontology, units, validation rules. Mentioned but not designed in v1.
- **Graph-layer representation of `consumed_by` and `produces:`.** If a future query consumer wants to traverse `plan → dataset → workflow-run → upstream dataset` in the knowledge graph, these backlinks need graph edges (`sci:consumesDataset`, `sci:producesDataset`). Frontmatter-only is sufficient for v1.
- **Datapackage drift reconciliation command.** When entity ↔ runtime drift, `science-tool dataset reconcile <slug> --apply` could rewrite the entity's cached fields from the runtime `datapackage.yaml`. Deferred until drift is observed.
- **Dataset entity generation from datapackage.** For projects that receive a datapackage from an upstream collaborator, `science-tool dataset from-datapackage <path>` could emit a dataset entity stub. Natural fit but not required by v1.
- **`science-tool dataset siblings regenerate <parent-slug>`.** Recomputes an umbrella entity's `siblings:` list from children's `parent_dataset`. Makes the cached view trivially re-derivable; addresses lineage drift.
- **Cross-plan consumption weights.** A richer `consumed_by` form recording which part of each plan consumes the dataset (single transformation, ancillary lookup, validation only), enabling impact queries. Not required by v1.
- **Spec Y prerequisites.** When Spec Y lands, datasets become a candidate for promotion to a datapackage-directory backend (the `data/<slug>/datapackage.yaml` IS the entity; no markdown sidecar). The science-pkg schema is unchanged; only the storage location and reader change.
