# Dataset Entity Lifecycle and `science-pkg` Schema

**Date:** 2026-04-19
**Status:** Draft (rev 2 — unified external + derived data)
**Supersedes:** rev 1 of this file (external-dataset-only access verification gate)
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

- A `science-pkg-1.0` JSON Schema published at `science-model/schemas/science-pkg-1.0.json`, conforming to Frictionless DataPackage with science-specific extensions. Validates both entity frontmatter and runtime `datapackage.yaml`.
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
- New: `science-tool dataset register-run <workflow-run-slug>` command — emits derived dataset entities from a completed run, idempotent.
- New: `science-tool dataset reconcile <slug>` command — checks entity ↔ runtime `datapackage.yaml` drift.
- Renamed entity type: `data-package` → `research-package`. New entity location: co-located with the rendered bundle at `research/packages/<lens>/<section>/research-package.md`. First entity type to live outside `doc/`.
- `research-package` carries `displays: [dataset:<slug>, ...]` referring to the derived datasets it renders. Provenance fields (workflow_run, inputs, etc.) are removed from `research-package` (now live on the derived datasets).
- `science-tool health` grows ten anomaly classes (rev 1's five plus five new for derivation, asymmetric edges, broken input chains, origin/block mismatch, research-package orphans).
- Per-entity-type discovery rule (small precursor to Spec Y's resolver): the graph builder gains a config mapping entity type → glob pattern, used for two paths in v1 (dataset under `doc/datasets/`, research-package under `research/packages/<...>/research-package.md`).
- Strict migration posture for the `data-package` → `research-package` rename: the graph builder fails with a descriptive error on any unmigrated `data-package` entity. No silent shim.

### Out of scope (v1)

- Multi-backend entity storage (datapackage-directory backend for datasets, aggregate-json backend for lightweight entities like rare topics). This is **Spec Y**, sibling to this spec, written immediately after v1 ships.
- Automated `science-tool dataset verify <slug>` (external verification automation). Documented as follow-on; v1 is structural-only.
- Automated `science-tool dataset stage <slug>` (materialize runtime `datapackage.yaml` from entity for external sources). Documented as follow-on.
- Automated `science-tool dataset migrate <slug>` (legacy flat-access → structured). Documented as follow-on.
- Automated `science-tool data-package migrate <slug>` (split data-package into dataset + research-package). Documented; manual migration is straightforward.
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
- **Derived:** Workflow rule produces output files + writes `results/<wf>/<run>/datapackage.yaml` (as it already does today). A terminal `register_dataset_entities` rule (or `science-tool dataset register-run`) splits the run's outputs into N logical `dataset` entities (one per declared output in the workflow's `outputs:` block), each with `origin: derived` and `derivation.workflow_run` pointing back. The same datapackage.yaml fields live in both the runtime file and the entity's frontmatter; drift is a health warning.

## The `science-pkg` Schema Family

Published as a single JSON Schema under `science-model/schemas/science-pkg-1.0.json`. Declared via Frictionless `profiles: ["science-pkg-1.0"]`. The schema validates both entity frontmatter and runtime `datapackage.yaml`. Differences between the two surfaces are which fields are *required*, not which fields are *allowed*.

**Top-level extensions beyond Frictionless DataPackage (`name`, `title`, `description`, `licenses`, `resources`):**

| Field | Type | Required when | Notes |
|---|---|---|---|
| `profiles` | array of string | always | MUST include `"science-pkg-1.0"` |
| `origin` | enum `external|derived` | always (entity surface) | Discriminator. Defaults to `external` for back-compat reading. |
| `tier` | enum `use-now|evaluate-next|track` | entity surface | Discovery priority. |
| `update_cadence` | enum | optional | `static|rolling|monthly|quarterly|annual|versioned-releases`. |
| `ontology_terms` | array of CURIE | optional | Domain semantic tags. |
| `datapackage` | string (relative path) | optional | Pointer from entity → runtime mirror. |
| `consumed_by` | array of `<type>:<slug>` | optional | Downstream consumers. Always allowed. |
| `parent_dataset` | `dataset:<slug>` | optional | Lineage (mostly external; allowed for derived). |
| `siblings` | array of `dataset:<slug>` | optional | Cached view; regenerable from children's `parent_dataset`. |
| `access` | object | required iff `origin == external` | Verification gate state. Forbidden when derived. |
| `derivation` | object | required iff `origin == derived` | Provenance. Forbidden when external. |
| `accessions` | array of string | optional, external only | External accession IDs (renamed from `datasets:`). |

**`access:` block** (unchanged from rev 1 except `datapackage` moves to top-level):

```yaml
access:
  level: public | registration | controlled | commercial | mixed
  verified: bool
  verification_method: retrieved | credential-confirmed | ""
  last_reviewed: YYYY-MM-DD
  verified_by: ""
  source_url: ""
  credentials_required: ""
  local_path: ""                 # single-file escape hatch
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

**Resources block** (Frictionless DataResource):

The standard Frictionless `resources[]` block carries per-resource `name`, `path`, `format`, `mediatype`, `bytes`, `hash`, `schema`. v1 does not extend per-resource; the `science_resource` extension is future work.

The entity's `resources[]` may be a thin mirror of the runtime `datapackage.yaml`. When the entity has `datapackage: <path>` set, the runtime file is canonical for the listed resources; entity-side `resources[]` is advisory and a `science-tool dataset reconcile` warning surfaces drift.

## Data Model

### Unified `dataset` entity — example, `origin: external`

```yaml
---
id: "dataset:li2021-nature-coding-snvs"
type: "dataset"
title: "Li 2021 Nature Supplementary Table 3 — coding SNVs"
status: "active"
profiles: ["science-pkg-1.0"]
origin: "external"

tier: "use-now"
license: "CC-BY-4.0"
update_cadence: "static"
ontology_terms: []

datapackage: "data/li2021-nature-coding-snvs/datapackage.yaml"
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
  local_path: ""
  exception:
    mode: ""
    decision_date: ""
    followup_task: ""
    superseded_by_dataset: ""
    rationale: ""

parent_dataset: "dataset:li2021"
siblings: []

resources:
  - name: "coding-snvs"
    path: "data/li2021-nature-coding-snvs/somatic_mutations.tsv"
    format: "tsv"
    mediatype: "text/tab-separated-values"
    bytes: 12345678
    hash: "sha256:..."
    schema:
      fields:
        - { name: "chr", type: "string" }
        - { name: "pos", type: "integer" }
        - { name: "ref", type: "string" }
        - { name: "alt", type: "string" }

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
profiles: ["science-pkg-1.0"]
origin: "derived"

tier: "use-now"
license: "internal"
update_cadence: "static"          # derived datasets are immutable per run
ontology_terms: []

datapackage: "results/theme-validation/r042/datapackage.yaml"

derivation:
  workflow: "workflow:theme-validation"
  workflow_run: "workflow-run:theme-validation-r042"
  git_commit: "abc1234"
  config_snapshot: "results/theme-validation/r042/config.yaml"
  produced_at: "2026-04-19T14:32:11Z"
  inputs:
    - "dataset:claims-corpus-2026-04"
    - "dataset:theme-taxonomy-v3"

resources:
  - name: "per-theme-kappa"
    path: "results/theme-validation/r042/per-theme-kappa.csv"
    format: "csv"
    mediatype: "text/csv"
    bytes: 234567
    hash: "sha256:..."
    schema:
      fields:
        - { name: "theme_id", type: "string" }
        - { name: "kappa", type: "number" }

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
    resources: ["per-theme-kappa.csv"]
    ontology_terms: []
  - slug: "structural-capability"
    title: "Structural capability table"
    resources: ["structural-capability.csv"]
    ontology_terms: []
```

Each declared output produces one derived `dataset` entity per workflow-run. The dataset's slug is `<workflow-slug>-<run-slug>-<output-slug>`. The dataset's `resources:` is the subset of the run's `datapackage.yaml` resources matching the declared `resources:` list.

## State Invariants

The schema implies ten machine-checkable rules. `science-tool health` surfaces violations as anomalies (severity per the table in the Health Check Additions section):

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

### Derived — workflow run → registration → planning downstream

```
Workflow run       Snakemake rule produces output files; writes
                     results/<wf>/<run>/datapackage.yaml as it does today.
    ↓
Registration       Terminal `register_dataset_entities` rule invokes:
                     science-tool dataset register-run workflow-run:<slug>
                   This reads the workflow's `outputs:` block and the run's
                   datapackage.yaml, then emits one derived dataset entity per
                   declared output:
                     origin: derived
                     derivation.workflow_run: workflow-run:<slug>
                     derivation.workflow: workflow:<slug>
                     derivation.git_commit: <commit>
                     derivation.config_snapshot: <path>
                     derivation.produced_at: <timestamp>
                     derivation.inputs: <runtime-resolved upstream datasets>
                     resources: <subset of run's resources matching output>
                     datapackage: results/<wf>/<run>/datapackage.yaml
                   Symmetric edge written to workflow-run.produces.
                   Idempotent: re-runs no-op with a drift warning.
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
Execution          Downstream pipeline reads from datapackage.yaml at the
                     entity's `datapackage:` path.
    ↓
Review             Dim 3 verifies symmetric edges, transitive input chain,
                     `consumed_by` backlinks, drift state.
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
- Per origin:
  - `external`: `access.verified: true` OR `access.exception.mode != ""`.
    `access.source_url` populated when verified.
    `access.last_reviewed` within the last 12 months.
  - `derived`: `derivation.workflow_run` exists; symmetric `produces:` edge
    present; `derivation.inputs` transitively pass.
- `consumed_by` includes `plan:<this-plan-file-stem>`.
- All ten state invariants hold for the entity.

Scoring:

- PASS — all sources resolve; gate satisfied per origin; backlink present;
  freshness OK; invariants hold.
- WARN — stale `last_reviewed` (> 12 months); missing canonical
  `plan:<stem>` backlink; entity ↔ runtime drift; lineage drift.
- FAIL — any of:
  - A source does not resolve to a dataset entity.
  - External `access.verified: false` with `access.exception.mode: ""`.
  - External `access.verified: true` but `verification_method: ""` or no
    `last_reviewed`.
  - Derived missing `workflow_run` entity, asymmetric `produces:` edge, or
    broken transitive input chain.
  - A plan references an umbrella entity (non-empty `siblings:`).
  - Origin/block-exclusion violation (#7 or #8).
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
science-tool dataset register-run <workflow-run-slug>  # emit derived entities
science-tool dataset reconcile <slug>                  # entity ↔ runtime drift check
```

`register-run` is idempotent: re-running on an already-registered run no-ops if the entity matches the current state, or warns + reports drift if the run's `datapackage.yaml` has changed.

`reconcile` exits non-zero if the entity's `resources[]`, `formats`, or `bytes` differ from the runtime `datapackage.yaml` at `<entity>.datapackage`.

**Follow-on (deferred):**

```bash
science-tool dataset verify <slug>                     # external automation
science-tool dataset stage <slug>                      # materialize runtime datapackage
science-tool dataset migrate <slug>                    # legacy → structured
science-tool data-package migrate <slug>               # split into dataset + research-package
```

## Health Check Additions

`science-tool health` grows ten anomaly classes (rev 1's five plus five new):

| Anomaly | Severity | Trigger |
|---|---|---|
| `dataset_consumed_but_unverified` | error | external entity has non-empty `consumed_by` but `access.verified: false` AND `access.exception.mode: ""` |
| `dataset_stale_review` | warning | external entity has `access.verified: true` but `last_reviewed` older than 12 months |
| `dataset_missing_source_url` | warning | external entity has `access.verified: true` but `access.source_url: ""` |
| `dataset_datapackage_drift` | warning | entity `resources[]` (and/or `formats`/`bytes`) differ from runtime `datapackage.yaml` at `entity.datapackage` |
| `dataset_invariant_violation` | warning | any of invariants #1, #2, #3, #4, #5, #6 false |
| `dataset_derived_missing_workflow_run` | error | derived entity's `derivation.workflow_run` doesn't resolve to a `workflow-run` entity |
| `dataset_derived_asymmetric_edge` | error | derived entity's `workflow-run` exists but doesn't list this dataset's ID in `produces:` |
| `dataset_derived_input_chain_broken` | error | derived entity's `derivation.inputs` transitively fails the gate (cycle, missing entity, or unverified leaf); error names the breaking link |
| `dataset_origin_block_mismatch` | error | invariant #7 or #8 violated (e.g., `access:` on derived; `derivation:` on external; `accessions:` on derived) |
| `dataset_research_package_orphan` | warning | `research-package.displays` references a dataset that doesn't exist OR isn't `origin: derived` |

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

Philosophy: opt-in, additive, no bulk rewrite. Existing files continue to parse via back-compat read rules. Migration is per-entity, triggered when a plan or workflow next touches the entity. **Strict posture for the `data-package` rename**: the graph builder fails with a descriptive error on any unmigrated `data-package` entity (no silent shim).

### Path 1 — Legacy `dataset.md` → unified `dataset` (rev 1 carry-forward)

- Flat `access: public|controlled|mixed` parses as `access.level: <value>` with all other subfields defaulting (`verified: false`, etc.). Origin defaults to `external` when not specified.
- `datasets: [...]` aliases to `accessions: [...]`.
- `science-tool dataset migrate <slug>` (deferred) automates rewrite.

Net: legacy externals continue to function; gate halts until verified or exception added.

### Path 2 — Existing `data-package` entity → split into derived `dataset` + `research-package`

`science-tool data-package migrate <slug>` (deferred but documented):

1. Reads `doc/data-packages/<slug>.md` and the linked `datapackage.json`.
2. Reads the workflow's `outputs:` block. If absent, prompts the user to add one or accept "one dataset per resource" as a fallback.
3. Emits N derived `dataset` entities (one per logical output) at `doc/datasets/<workflow>-<run>-<output>.md`, with `derivation:` populated from the data-package's existing `provenance` block.
4. Emits one `research-package` entity at `research/packages/<lens>/<section>/research-package.md`, with `displays:` listing the N derived datasets and the existing narrative bundle (`cells.json`, `figures`, `vegalite_specs`, `code_excerpts`) preserved.
5. Marks the old `doc/data-packages/<slug>.md` with `status: superseded`. The file is not deleted; git history preserves it.

**Strict mode:** until `science-tool data-package migrate` is run for every existing `data-package` entity, the graph build fails with: `unmigrated data-package entity '<slug>'; run 'science-tool data-package migrate <slug>' to split into dataset + research-package`. The error names every offending slug.

### Path 3 — Existing `workflow.md` → add `outputs:` block

Workflows currently have no `outputs:` declaration. Adding one is opt-in.

- Workflows without `outputs:` continue to run; their runs don't auto-register derived datasets.
- Plans that try to consume those runs' outputs halt at the gate until the workflow gains `outputs:` AND its terminal `register_dataset_entities` rule runs.

A `science-tool workflow add-outputs <slug>` helper (deferred) walks an existing workflow's most recent `datapackage.json` and offers an interactive grouping into logical outputs.

### Path 4 — Existing `workflow-run.md` → gains `produces:` and `inputs:`

Pure additive. Old workflow-run entities continue to parse with empty implicit lists. The `register-run` command populates `produces:`/`inputs:` for new runs. Historical runs may be left unmigrated unless a downstream plan needs to query them.

### Recommended migration sequence

1. **Day 0** (this spec lands): no change required. Existing entities continue to parse; gate halts only fire when a *new* plan is drafted against an unmigrated entity.
2. **Pre-migration step (one-time)**: list existing `data-package` entities (`science-tool data-package list` — also deferred but trivial). For each, decide on the workflow's `outputs:` block. Either add `outputs:` and run `data-package migrate <slug>`, or accept the fallback grouping.
3. **As needed**: when a new plan touches a legacy external dataset, the gate halts → user migrates that one entity (verify or add exception).
4. **As needed**: when a workflow gets a new `outputs:` block + the register rule, future runs auto-emit derived dataset entities.

**No data file movement.** Migration touches `doc/`, `research/packages/`, `templates/` only. Runtime `datapackage.yaml` files stay in place; new derived dataset entities point at them.

## Testing

### Unit tests

`science-tool/tests/test_science_pkg_schema.py`:
- All ten invariants tested with synthetic frontmatter triggering each violation.
- `origin: external` and `origin: derived` shapes parse; missing `origin:` defaults to `external`.
- Per-origin block requirement (#7, #8): `derivation:` on external rejects, `access:` on derived rejects.
- Frictionless validation: `resources[]` shape conforms to Frictionless DataResource schema.

`science-tool/tests/test_dataset_entity.py`:
- Legacy flat `access: public` parses to `access.level: public, verified: false`.
- Legacy `datasets:` aliases to `accessions:`.
- New `derivation:` block parses with all fields.
- Schema validation produces same errors at parse time as raw schema test.

`science-tool/tests/test_health_dataset.py`:
- Each of the ten anomaly classes fires for its trigger; doesn't fire when absent.
- Transitive `dataset_derived_input_chain_broken` walks the chain and reports the breaking link by name.

`science-tool/tests/test_dataset_cli.py`:
- `dataset list --origin external|derived` filters correctly.
- `dataset register-run <run>` emits N entities matching the workflow's `outputs:` declaration; idempotent (re-run produces no diff).
- `dataset reconcile <slug>` exits non-zero on drift; zero when in sync.
- `dataset consumers <slug>` returns `consumed_by` list; works for both origins.

`science-tool/tests/test_data_package_migration.py`:
- `data-package migrate <slug>` produces N derived datasets + 1 research-package matching the workflow's `outputs:`.
- Old `data-package` file gets `status: superseded`.
- Strict mode: graph build fails with descriptive error when any unmigrated `data-package` entity is found; error names the slug and points at the migrate command.

### Integration tests

`science-tool/tests/test_plan_pipeline_data_gate.py` (extends rev 1):
- Plan against verified external input: passes Step 2b, Step 4.5 appends backlink.
- Plan against derived input pointing at registered run: passes.
- Plan against derived input whose `derivation.workflow_run` doesn't exist: halts.
- Plan against derived input with asymmetric `produces:` edge: halts with invariant violation.
- Plan against derived input whose chain contains an unverified external: halts with broken-link path printed.

`science-tool/tests/test_review_pipeline_dim3.py`:
- Mixed-origin pipeline: PASS when each branch's gate is satisfied; FAILs surface per item.
- WARN tier triggers (stale `last_reviewed`, missing backlink).

`science-tool/tests/test_workflow_registration.py`:
- End-to-end with toy workflow + `outputs:` declaration: terminal `register_dataset_entities` rule emits derived dataset entities; gate accepts a downstream plan; asymmetric edges and missing entities both detected.

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
- **`commands/health.md`** / `science-tool health` — adds five anomaly classes beyond rev 1.
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
- **Strict migration for the `data-package` rename.** Graph builder fails on unmigrated entities. Few projects affected; trades upfront effort for reduced code complexity. No silent shim.
- **`origin: external` default for back-compat reading.** Pre-rev-2 `dataset.md` entries continue to parse as `origin: external`.
- **No symlinks.** The runtime `datapackage.yaml` is a real file written by the workflow (derived) or materialized by `dataset stage` (external). Symlinks were rejected because the runtime file may evolve independently (per-resource hashes after staging, schemas inferred from data) and because diff/git ergonomics suffer.
- **Forward-compatibility with Spec Y.** This spec's schema is identical regardless of storage backend. Spec Y can later promote datasets to a datapackage-directory backend without changing the science-pkg schema.

## Follow-on Work

- **`science-tool dataset verify <slug>`.** Automates the external verification flip for public URLs (retrieve → SHA256 → flip `verified: true` with `verification_method: "retrieved"` → append log). Interactive prompt for controlled sources (records `credential-confirmed`).
- **`science-tool dataset stage <slug>`.** Materializes the runtime `datapackage.yaml` from the entity for external sources at staging time.
- **`science-tool dataset migrate <slug>`.** Rewrites legacy flat `access: <level>` and `datasets: [...]` fields into the structured schema.
- **`science-tool data-package migrate <slug>`.** Splits an existing data-package into derived `dataset` entities + a `research-package` entity. Idempotent; safe to run in bulk.
- **`science-tool workflow add-outputs <slug>`.** Interactive helper for adding the `outputs:` block to legacy workflows.
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
