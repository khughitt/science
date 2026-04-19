# Dataset Entity Lifecycle

**Date:** 2026-04-19
**Status:** Draft

## Motivation

Every research project has external data inputs. The point at which access to those inputs should be verified is **before detailed pipeline planning begins** — discovering that a dataset is actually controlled-access mid-implementation forces scope decisions under time pressure, invalidates in-progress work, and leaves the project without a durable record of what was tried.

The framework already has most of the pieces:

- `templates/dataset.md` defines a `dataset` entity with discovery fields (`tier`, `access`, `license`, `formats`, ontology terms).
- `commands/find-datasets.md` creates `doc/datasets/<slug>.md` entries during dataset discovery.
- `commands/review-pipeline.md` has a shallow Dim 3 "Data Availability" rubric item.

What is missing:

1. The dataset entity has no concept of **access verification state** — there is no machine-readable "has someone actually confirmed this is retrievable under current credentials, and when?". `access: public | controlled | mixed` is aspirational; a value at discovery time, not a gate.
2. There is no **backlink** from the dataset entity to the plans/pipelines/workflows that consume it. A user cannot answer "what does this dataset depend on?" or "what depends on this dataset?" without grep.
3. `/science:plan-pipeline` has no explicit data-access gate — it moves straight from inquiry loading to transformation planning. Real projects have rediscovered the "oh, this dataset is dbGaP-only" failure mode multiple times at the wrong moment.
4. `/science:review-pipeline` Dim 3 checks that a source is "specified" but not that its access has been **verified**. The gap between "we wrote down a URL" and "someone actually retrieved from it" is where this failure mode lives.
5. Granularity is collapsed: one paper with both a public supplement (coding SNVs) and a controlled EGA deposit (raw WES) currently maps to a single dataset entity with `access: mixed`, which hides which access level applies to which artefact.

The concrete case that triggered this spec: a cbioportal task (t111) discovered mid-implementation that Xu 2025's per-variant calls were dbGaP-only despite the paper being published. A post-hoc data-access gate was added to the task's plan document — a one-off file with a bespoke format. The insight is that this information belongs on the dataset entity itself, not in a sibling plan artefact.

## Goal

Extend the `dataset` entity to be the single authority for access state, and route `/science:plan-pipeline`, `/science:review-pipeline`, and `/science:find-datasets` through it. Every external data input referenced by a plan resolves to a `dataset:<slug>` entity with a verified `access.verified: true` state before pipeline detail is written. The dataset entity also carries a downstream-consumer backlink, enabling coverage and impact queries without manual grep.

The data package (`datapackage.json`) remains the workhorse for **resource-level** machine-readable metadata (paths, checksums, schemas, formats). The dataset entity carries **discovery-level narrative + gate state** and links out to a data package once one is produced.

## Design Principles

- **The dataset entity is the authority for access state; the data package is the authority for resource state.** No duplicated fields. When both exist, the data package's resource-level metadata is canonical; the entity links to it.
- **Access state is binary + dated.** `access.verified: true|false` plus `access.last_reviewed` is sufficient for v1. No state machine; no automated expiry enforcement; `last_reviewed` is a soft staleness signal, not a gate.
- **Granularity follows artefact, not paper.** A paper with one public supplement and one controlled raw-read deposit produces two sibling dataset entities with `parent_dataset` linking them.
- **Plans consume dataset entities, not URLs.** `/science:plan-pipeline` and `/science:review-pipeline` resolve inputs through `dataset:<slug>` references. Unknown inputs dispatch to `/science:find-datasets` rather than being enumerated inline.
- **No silent fallback on verification state.** If `access.verified` is `false` and a plan tries to consume the entity, the command halts and surfaces Branch A/B options (scope-reduce / expand / substitute). This matches the framework's general fail-early posture.
- **Prose stays human-authored.** Verification logs, granularity notes, and access narrative remain markdown prose — structured where it pays (frontmatter), unstructured where it doesn't (log entries).

## Scope

### In scope (v1)

- Frontmatter extension on `templates/dataset.md`: structured `access:` block (replacing the flat `access: public|controlled|mixed` field), `parent_dataset` / `siblings` lineage, `consumed_by` backlink.
- Two new prose sections on dataset entities: "Access verification log" (append-only) and "Granularity at this access level" (narrative of what this entity covers vs sibling entities).
- `/science:plan-pipeline` Step 2b: Data-access gate. Every input data source resolves to a dataset entity; every entity must be `access.verified: true`; unresolved or unverified inputs halt the plan with Branch A/B options.
- `/science:review-pipeline` Dim 3: upgraded checks against the dataset-entity state rather than plan-local URL text.
- `/science:find-datasets`: emit one entity per distinguishable artefact when a paper has multiple access levels. Newly-created entities start with `access.verified: false`.
- `science-tool health` anomalies: "entity has `consumed_by` entries but `access.verified: false`", "entity has `verified: true` but `last_reviewed` > N months ago" (warning tier only, no enforcement).

### Out of scope (v1)

- Automated verification CLI (`science-tool dataset verify <slug>`). Proposed as follow-on; v1 is structural-only.
- Automated `last_reviewed` expiry enforcement. v1 surfaces staleness; it does not block pipelines on stale reviews.
- Migration of existing `doc/datasets/*.md` entries to the new frontmatter. Existing entries continue to parse under an additive schema; deprecation of the flat `access:` field is deferred.
- Propagation of `consumed_by` backlinks to the RDF knowledge graph. Frontmatter-only for v1; graph-layer representation can follow once a consumer requires it.
- Per-resource SHA256 / size / format in the dataset entity. Those live in `datapackage.json`; the entity links but does not duplicate.
- Cross-project dataset-entity sharing. Each project carries its own `doc/datasets/` even if multiple projects reference the same upstream source. Shared dataset catalogues are a larger question for later.

## Data Model

### Extended `dataset.md` frontmatter

Replaces the existing flat `access: public | controlled | mixed` field with a structured `access:` block, adds lineage and backlink fields, leaves existing discovery fields (`tier`, `license`, `formats`, `size_estimate`, `update_cadence`, `ontology_terms`, `source_refs`, `related`) intact.

```yaml
---
id: "dataset:<granular-slug>"             # one entity per artefact, not per paper
type: "dataset"
title: "<Dataset Name — artefact-level specific>"
status: "active"

# Discovery (unchanged)
tier: "evaluate-next"                     # use-now | evaluate-next | track
license: ""                               # SPDX or "unknown"
formats: []                               # e.g., ["tsv", "h5ad"]
size_estimate: ""                         # e.g., "12 GB", "unknown"
update_cadence: ""                        # static | rolling | monthly | ...
ontology_terms: []

# Access block (new structured form)
access:
  level: "public"                         # public | registration | controlled | commercial
  verified: false                         # has someone actually retrieved under current credentials?
  last_reviewed: ""                       # YYYY-MM-DD; soft staleness signal, no enforcement
  verified_by: ""                         # agent/user who last ran the check
  source_url: ""                          # canonical discovery URL
  credentials_required: ""                # "dbGaP DAR phs000424.v7" | "" for public
  datapackage: ""                         # relative path to datapackage.json once staged

# Lineage (new)
parent_dataset: ""                        # optional: sibling-artefact link to umbrella entity
siblings: []                              # optional: reverse listing by the parent

# Consumer backlink (new)
consumed_by: []                           # ["task:t111", "workflow:extract_normal_tissue_spectra", ...]

# Pointers (existing; retained)
source_refs: []                           # cite:<paper>
related: []                               # topic:/question:/article:

# Housekeeping
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---
```

### Access level vocabulary

The `access.level` field takes one of five values:

| Level | Meaning | Examples |
|---|---|---|
| `public` | Retrievable without authentication | bioRxiv supplements, NCBI SRA open, Zenodo, Springer Nature MOESM files |
| `registration` | Free account, no approval step | Some Synapse projects, COSMIC non-commercial tier |
| `controlled` | Requires DAR/DUA + institutional review | dbGaP `phs*`, EGA `EGAD*`/`EGAC*`, AACR GENIE BPC, ICGC restricted, TCGA controlled-access |
| `commercial` | Requires paid license | DrugBank, some COSMIC redistribution tiers |
| `mixed` | This entity aggregates artefacts at multiple levels (discouraged; prefer granular siblings) | — |

The `mixed` value is retained for backward compatibility but should not be used for new entities — prefer emitting multiple granular entities linked via `parent_dataset`.

### Access block semantics

- **`verified: false`** means "no one has confirmed this is retrievable under current credentials." This is the default when `/science:find-datasets` creates a candidate entity.
- **`verified: true`** means someone has either (a) successfully downloaded the `source_url` and confirmed it matches the expected artefact, or (b) confirmed credentials-gated access (DAR letter on file, commercial license active). The `last_reviewed` date records when.
- **`last_reviewed`** is a soft staleness signal. `science-tool health` may warn on old values; commands do not block on stale reviews.
- **`verified_by`** captures agent identity for audit trails. Format: free text; typical values are `"claude"`, `"keith"`, `"claude+keith"` for collaborative verification.
- **`source_url`** is the discovery-level canonical URL. Resource-level URLs (per-file download links, per-sample accessions) live in the linked `datapackage.json`.
- **`credentials_required`** is empty for `public` and `registration` levels; populated with the specific accession/DAR reference for `controlled` and a license name for `commercial`.
- **`datapackage`** is a relative path to a staged `datapackage.json`. Empty until staging produces one; populated by the staging step.

### Lineage: `parent_dataset` and `siblings`

A paper or source with multiple artefacts at different access levels produces multiple entities. Example:

```yaml
# doc/datasets/li2021.md (umbrella)
id: "dataset:li2021"
title: "Li 2021 — body map of somatic mutagenesis in normal tissues"
access:
  level: "mixed"
  verified: false          # the umbrella entity is aspirational; siblings are authoritative
siblings:
  - "dataset:li2021-nature-coding-snvs"
  - "dataset:li2021-ega-wes-fastqs"
```

```yaml
# doc/datasets/li2021-nature-coding-snvs.md (public sibling)
id: "dataset:li2021-nature-coding-snvs"
title: "Li 2021 Nature Supplementary Table 3 — coding SNVs"
access:
  level: "public"
  verified: true
  source_url: "https://static-content.springer.com/..."
  credentials_required: ""
parent_dataset: "dataset:li2021"
```

```yaml
# doc/datasets/li2021-ega-wes-fastqs.md (controlled sibling)
id: "dataset:li2021-ega-wes-fastqs"
title: "Li 2021 EGA WES FASTQs"
access:
  level: "controlled"
  verified: false
  credentials_required: "EGA DAC EGAC00001002218"
parent_dataset: "dataset:li2021"
```

Plans reference the specific sibling they consume (`dataset:li2021-nature-coding-snvs`), not the umbrella. The umbrella exists for narrative and discovery only.

### `consumed_by` backlink

Each dataset entity lists the plans, tasks, or workflows that consume it. Populated by `/science:plan-pipeline` during planning; read by `/science:review-pipeline` and `science-tool health` for coverage checks.

```yaml
consumed_by:
  - "task:t111"
  - "plan:2026-04-18-t111-normal-tissue-spectra-plan"
  - "workflow:extract_normal_tissue_spectra"
```

Format: list of entity references using the existing `<type>:<slug>` convention. No schema enforcement on entity-type membership in v1; inverse lookups via `science-tool dataset consumers <slug>` parse the field as-is.

### Prose sections

Two new prose sections on dataset entity documents:

**Access verification log** (append-only, chronological):

```markdown
## Access verification log

- 2026-03-15 (claude+keith): DAR submitted to dbGaP for phs000424.v7 — pending review.
- 2026-04-19 (claude): DAR still pending; Branch B — scoped out of t111, deferred to t112.
- 2026-04-19 (claude): Alternative artefact dataset:li2021-nature-coding-snvs verified public,
  SHA256 matches; staged at data/li2021_somatic_mutations.tsv via
  code/scripts/stage_li2021_somatic_mutations.py.
```

The log is the audit trail; the frontmatter `access` block is the current state.

**Granularity at this access level** (narrative):

```markdown
## Granularity at this access level

- Supplementary Table 3 (this entity): coding SNVs only, ~66k rows, post-filter ~55k SBS.
- Raw WES/WGS (controlled, see sibling dataset:li2021-ega-wes-fastqs): per-read data required
  for non-coding analysis. Not accessible without DAR.
```

This section explicitly distinguishes what this entity's access level covers vs what a sibling entity covers, preventing the "data is published" / "per-record is gated" confusion.

### Relationship to data packages

A `datapackage.json` (Frictionless standard) is the structured successor to several dataset-entity fields. Once staging produces a datapackage, the following fields are considered authoritative in the datapackage:

- `resources[].path` — concrete file paths
- `resources[].hash` — SHA256 / MD5 per resource
- `resources[].format`, `resources[].mediatype` — per-resource format
- `resources[].schema` — per-resource column schema
- `resources[].bytes` — per-resource size

The dataset entity's top-level `formats`, `size_estimate`, and `access.source_url` remain populated at discovery time (pre-staging). Once `access.datapackage` is set, they become cached/aspirational duplicates of the authoritative datapackage values. `science-tool health` may surface drift between entity frontmatter and linked datapackage as a soft warning.

The dataset entity is **not** a Frictionless Data Package. It is a discovery + narrative + gate artefact that points to a datapackage. Conversely, a datapackage does not carry the `verified` / `last_reviewed` / `consumed_by` / narrative fields — those belong on the entity.

## Lifecycle

```
Discovery          /science:find-datasets creates doc/datasets/<slug>.md with:
                     access.verified: false
                     access.level: <best-guess from LLM knowledge + repo metadata>
                     consumed_by: []
    ↓
Verification       Manually (log entry) or via future `science-tool dataset verify`:
                     retrieve source_url → check against expectations → flip
                     access.verified: true + populate last_reviewed + verified_by
                     + append a log entry
    ↓
Planning           /science:plan-pipeline §Step 2b:
                     resolve each input to dataset:<slug>
                     enforce access.verified: true
                     append plan to consumed_by
    ↓
Execution          Staging code reads from the path implied by access.datapackage
                     (or directly from source_url if no datapackage has been materialized).
                     Run produces outputs and optionally a new datapackage for the outputs.
    ↓
Review             /science:review-pipeline Dim 3:
                     verify every input resolved to a dataset entity
                     verify access.verified: true
                     verify consumed_by contains this plan
                     WARN if last_reviewed is stale
```

## Command integrations

### `/science:find-datasets`

- Emit one dataset entity per distinguishable artefact at a distinct access level. A paper with one public supplement and one controlled EGA deposit produces two entities plus optionally a third umbrella entity linking them via `parent_dataset` / `siblings`.
- New entities start with `access.verified: false`, `access.last_reviewed: ""`, `consumed_by: []`.
- Populate `access.level`, `access.source_url`, and `access.credentials_required` from discovery evidence. When uncertain, use the most restrictive known level; the verification step corrects.

### `/science:plan-pipeline` — new Step 2b: Data-access gate

Inserted between the existing Step 2 (identify computational requirements) and Step 3 (add computational nodes to the inquiry). Runs in both Inquiry and Task modes.

```markdown
### Step 2b: Data-access gate (both modes)

For each input data source identified in Step 2:

1. Resolve to a `dataset:<slug>` entity. If no entity exists, invoke
   `/science:find-datasets` to create one. Do not proceed with a URL alone.
2. Check `access.verified`. If `false`, halt and raise to the user:
   - **Branch A**: entity is verifiable under current credentials — run verification
     (manual update or future `science-tool dataset verify`), then re-run this step.
   - **Branch B**: entity requires credentials the project does not hold. Three options:
     (a) reduce scope to accessible sources only; defer this one to a follow-up task
     (b) add credential acquisition to the current task (document the DAR/DUA timeline)
     (c) substitute an alternative open-access dataset covering the same role
3. Once the input is `access.verified: true`, append the current plan's ID to the
   entity's `consumed_by` list.
4. Record the gate outcome in the dataset entity's verification log. If Branch B was
   chosen, the log entry names which option (a/b/c) and any follow-up task that will
   eventually pick up the deferred source.
```

### `/science:review-pipeline` Dim 3 upgrade

Existing Dim 3 ("Data Availability") replaced with the entity-resolution check:

```markdown
#### Dimension 3: Data Availability

For each input data source (every `BoundaryIn` node or data-acquisition step):

- Does it resolve to a `dataset:<slug>` entity in `doc/datasets/`?
- Is the entity's `access.verified: true`?
- Is `access.source_url` populated? (Discovery URL, not per-resource URLs.)
- Does the entity's `consumed_by` list include the current plan?
- Is `access.last_reviewed` within the last 12 months?

**Scoring:**
- **PASS** — all sources resolve; all `access.verified: true`; `consumed_by` lists the plan;
  `last_reviewed` fresh.
- **WARN** — some sources have stale `last_reviewed` (> 12 months), OR `consumed_by` doesn't
  list this plan (backlink missing), OR some sources resolve but have incomplete entity
  metadata (missing `source_url`, no verification log entry).
- **FAIL** — any source does not resolve to a dataset entity, OR any source has
  `access.verified: false` without a documented Branch-B fallback, OR `access.verified: true`
  without a `last_reviewed` value.
```

## CLI affordances

New `science-tool dataset` subcommands. v1 includes only the read-side commands; the write-side `verify` is documented here for follow-on work.

**v1 (read-only):**

```bash
science-tool dataset list                              # all entities
science-tool dataset list --unverified                 # access.verified: false
science-tool dataset list --stale-review --months 12   # last_reviewed > N months ago
science-tool dataset list --level controlled           # filter by access.level
science-tool dataset consumers <slug>                  # reverse lookup via consumed_by
science-tool dataset show <slug>                       # full entity view
```

**Follow-on (write-side, deferred):**

```bash
science-tool dataset verify <slug>                     # flip verified: true, update last_reviewed
                                                       # for public level: retrieves source_url,
                                                       # confirms response; prompts for SHA256
                                                       # for controlled level: interactive prompt
                                                       # that records credential state + log entry
```

## Health check additions

`science-tool health` grows three anomaly classes tied to the new schema:

| Anomaly | Severity | Trigger |
|---|---|---|
| `dataset_consumed_but_unverified` | error | entity has `consumed_by: [...]` but `access.verified: false` |
| `dataset_stale_review` | warning | entity has `access.verified: true` but `last_reviewed` older than 12 months (configurable) |
| `dataset_missing_source_url` | warning | entity has `access.verified: true` but `access.source_url: ""` |
| `dataset_datapackage_drift` | warning | entity's frontmatter `formats`/`size_estimate` differs from its linked `datapackage.json` |

The `dataset_consumed_but_unverified` anomaly is the strongest signal that a plan is about to fail at execution time; it fires whenever a pipeline references a dataset the project hasn't actually confirmed access to.

## Template Updates

Replace `templates/dataset.md` with the extended version described in the Data Model section above. Existing dataset documents that carry only the flat `access: public|controlled|mixed` field continue to parse under the additive schema; `access.verified` defaults to `false` when the structured form is absent, which surfaces them in `science-tool dataset list --unverified` for backfill.

Migration is opt-in per entity — no bulk rewrite. When a plan is drafted against an un-migrated dataset entity, `/science:plan-pipeline` §Step 2b halts because `access.verified: false`, which prompts the user to either run verification (moving the entity to the new schema) or mark the entity as Branch B.

## Testing

### Unit tests

In `science-tool/tests/test_dataset.py`:

- An entity with only the flat `access: public` field parses under the new schema with `access.verified` defaulting to `false`.
- An entity with a structured `access:` block parses all fields correctly.
- `science-tool dataset list --unverified` lists exactly entities with `access.verified: false`.
- `science-tool dataset consumers <slug>` returns the `consumed_by` list for the named entity.
- Health check fires `dataset_consumed_but_unverified` when `consumed_by` is non-empty and `verified` is false.

### Integration tests

In `science-tool/tests/test_plan_pipeline_data_gate.py`:

- A plan-pipeline run against a task whose inputs resolve to a `verified: true` dataset completes normally, appending the plan to `consumed_by`.
- A plan-pipeline run against a task whose inputs have no dataset entity halts and calls out the missing entity.
- A plan-pipeline run against a task with a `verified: false` dataset halts with Branch A/B options in the output.

## Relationship to Existing Specs

- **Existing `templates/dataset.md`** — this spec replaces the template; the migration is backward-compatible (existing files parse; new fields default safely).
- **`commands/find-datasets.md`** — this spec amends the emission rules (one entity per artefact-level; default `verified: false`). No conflict.
- **`commands/plan-pipeline.md`** — this spec adds §Step 2b. The existing Rules section also grows three MUSTs; no other sections change.
- **`commands/review-pipeline.md`** — this spec rewrites Dim 3. No other dimensions change.
- **`commands/health.md`** / `science-tool health` — this spec adds four anomaly classes.
- **Frictionless data-package skill** — this spec references the datapackage as the authoritative resource-level representation; no changes to the data-package skill itself are required.
- **2026-04-19 entity-aspects spec** — orthogonal. Dataset entities may eventually carry `aspects:` like other entities; v1 does not address this.

## Resolved Decisions

- **Granularity: one entity per artefact.** A paper with a public supplement and a controlled raw-read deposit produces separate entities linked via `parent_dataset` / `siblings`. The previous `access: mixed` flag is retained for backward compatibility but not recommended for new entities.
- **Staleness: `last_reviewed` only; no automatic expiry enforcement.** v1 surfaces stale reviews as warnings in health and review-pipeline; it does not block pipelines on stale reviews.
- **Data-package relationship: reference, not duplicate.** Resource-level metadata (SHA256s, paths, schemas, sizes) lives in `datapackage.json`. The dataset entity carries discovery, narrative, access-state, and lineage. Cached entity-level fields (`formats`, `size_estimate`) are advisory once a datapackage exists.
- **Gate record location: on the dataset entity.** No separate `doc/plans/<slug>-data-gate-record.md` artefact. The dataset entity's frontmatter is the current state; the "Access verification log" section is the audit trail.
- **Verification automation: deferred to follow-on.** v1 is structural-only. `science-tool dataset verify` is documented but not implemented in v1.

## Follow-on Work

- **`science-tool dataset verify <slug>` CLI.** Automates the flip for public URLs (retrieve → SHA256 → flip `verified` → append log). Interactive prompt for controlled sources. Deferred because v1's structural change is independently valuable and the automation surface benefits from seeing real-world usage patterns first.
- **`last_reviewed` expiry enforcement.** If stale-review warnings go unactioned in practice, consider upgrading them to errors with a configurable threshold. Not required until data accumulates on whether 12 months is the right default.
- **Shared cross-project dataset catalogue.** When multiple projects reference the same Li 2021 supplementary table, duplicating the entity is wasteful. A framework-level shared catalogue (perhaps under `~/d/science/data/datasets/`) would let projects inherit and layer project-specific `consumed_by` onto a canonical entity. Non-trivial; defer.
- **Graph-layer representation of `consumed_by`.** If a future query consumer wants to traverse "plan → dataset → dataset's verification log" in the knowledge graph, the backlink will need a graph edge (e.g., `sci:consumesDataset`). Frontmatter-only is sufficient for v1.
- **Datapackage drift reconciliation command.** When the dataset entity's cached `formats` / `size_estimate` drift from the linked datapackage, `science-tool dataset reconcile <slug>` could rewrite the entity's cached fields from the datapackage. Deferred until drift is observed in practice.
- **Dataset entity generation from datapackage.** For projects that receive a datapackage from an upstream collaborator, a `science-tool dataset from-datapackage <path>` command could emit a dataset entity stub with access metadata. Natural fit but not required by v1.
