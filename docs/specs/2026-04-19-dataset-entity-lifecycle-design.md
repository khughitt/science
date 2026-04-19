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
- **Access state is structured + dated.** `access.verified: true|false` is not enough on its own; verification must record its **method** (`retrieved` vs `credential-confirmed`) and its `last_reviewed` date. No state machine beyond those three fields; `last_reviewed` is a soft staleness signal, not an automatic gate.
- **Branch decisions are machine-readable.** A Branch-B outcome (scope-reduce / expand / substitute) is recorded in a structured `access.exception:` block, not only in prose. The prose log remains for narrative; rubric checks read the structured form.
- **Granularity follows artefact, not paper.** A paper with one public supplement and one controlled raw-read deposit produces two sibling dataset entities linked via `parent_dataset` (authoritative); umbrella `siblings:` listings are optional cached views.
- **Plans consume dataset entities by stable ID.** `/science:plan-pipeline` and `/science:review-pipeline` resolve inputs through `dataset:<slug>` references. Unknown inputs dispatch to `/science:find-datasets` rather than being enumerated inline. Plans are identified as `plan:<plan-file-stem>`; the backlink is written only after the plan file exists.
- **Execution reads from the datapackage, not the discovery URL.** `access.source_url` is for verification and first-time retrieval. Once a datapackage exists, pipeline execution consumes concrete resources enumerated in it; `source_url` never becomes the runtime path.
- **No silent fallback on verification state.** If `access.verified` is `false` without a structured exception, commands halt and surface Branch A/B options. Matches the framework's general fail-early posture.
- **Prose stays human-authored.** Verification logs, granularity notes, and access narrative remain markdown prose — structured where it pays (frontmatter, exception block), unstructured where it doesn't (log entries).

## Scope

### In scope (v1)

- Frontmatter extension on `templates/dataset.md`: structured `access:` block (replacing the flat `access: public|controlled|mixed` field with `level`, `verified`, `verification_method`, `last_reviewed`, `verified_by`, `source_url`, `credentials_required`, `datapackage`, `local_path`, `exception`), `parent_dataset` lineage (authoritative), optional `siblings` cache, `consumed_by` backlink, `accessions:` field (renames / aliases the existing `datasets:` field).
- Two new prose sections on dataset entities: "Access verification log" (append-only) and "Granularity at this access level".
- A "State invariants" section in this spec listing six machine-checkable rules the schema implies.
- `/science:plan-pipeline` Step 2b: Data-access gate. Every input data source resolves to a dataset entity; unverified inputs without a structured `access.exception` halt the plan with Branch A/B options. `consumed_by` is appended in a new Step 4.5, after the plan file is written, using the canonical `plan:<plan-file-stem>` identity.
- `/science:review-pipeline` Dim 3: upgraded to check dataset-entity state, including the structured exception field and verification method.
- `/science:find-datasets`: emit one entity per distinguishable artefact when a paper has multiple access levels. Newly-created entities start with `access.verified: false`. Prior `datasets:` field renames to `accessions:` with read-time alias for back-compat.
- `science-tool health` anomalies: `dataset_consumed_but_unverified`, `dataset_stale_review`, `dataset_missing_source_url`, `dataset_datapackage_drift`, `dataset_invariant_violation` (warning tier, no enforcement).

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

# Discovery (unchanged from current template)
tier: "evaluate-next"                     # use-now | evaluate-next | track
license: ""                               # SPDX or "unknown"
formats: []                               # e.g., ["tsv", "h5ad"]
size_estimate: ""                         # e.g., "12 GB", "unknown"
update_cadence: ""                        # static | rolling | monthly | ...
ontology_terms: []

# Accession IDs (renamed from `datasets:` — old name soft-deprecated but still read)
accessions: []                            # e.g., ["EGAD00001007859", "phs000424.v7", "GSE12345"]

# Access block (structured)
access:
  level: "public"                         # public | registration | controlled | commercial
  verified: false                         # has someone confirmed access under current credentials?
  verification_method: ""                 # "retrieved" | "credential-confirmed" | ""
  last_reviewed: ""                       # YYYY-MM-DD; soft staleness signal, no enforcement
  verified_by: ""                         # agent/user who last ran the check
  source_url: ""                          # canonical discovery URL (verification + first retrieval)
  local_path: ""                          # optional: explicit staging path when no datapackage
  credentials_required: ""                # "dbGaP DAR phs000424.v7" | "" for public
  datapackage: ""                         # relative path to datapackage.json — authoritative at runtime
  exception:                              # populated iff verified: false but consumption is allowed
    mode: ""                              # "" | "scope-reduced" | "expanded-to-acquire" | "substituted"
    decision_date: ""                     # YYYY-MM-DD
    followup_task: ""                     # e.g., "task:t112"
    superseded_by_dataset: ""             # e.g., "dataset:li2021-nature-coding-snvs"; set iff mode="substituted"
    rationale: ""                         # one-line why

# Lineage
parent_dataset: ""                        # authoritative: child → parent
siblings: []                              # optional cached view on the parent entity; regenerable

# Consumer backlink — written in plan-pipeline Step 4.5, not Step 2b
consumed_by: []                           # ["plan:<plan-file-stem>", ...] — see consumed_by semantics

# Pointers (existing; retained)
source_refs: []                           # cite:<paper>
related: []                               # topic:/question:/article:

# Housekeeping
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---
```

The full schema appears long; in practice most fields are empty strings or empty lists at entity creation. A freshly-created public-dataset entity populates only `id`, `type`, `title`, `tier`, `accessions`, `access.level`, `access.source_url`, `source_refs`, `created`, `updated`. The rest are filled in as the lifecycle progresses.

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

- **`verified: false`** means "no one has confirmed this is accessible under current credentials." Default for `/science:find-datasets` output.
- **`verified: true`** means someone has confirmed access AND recorded how via `verification_method`. `verified: true` with `verification_method: ""` is an invariant violation.
- **`verification_method`** records how verification was established:
  - **`retrieved`** — someone actually pulled the canonical artefact (public URL or credentialed download) and confirmed it matches expectations. Strongest form.
  - **`credential-confirmed`** — authorization exists (DAR letter on file, commercial license active, account credentials tested) but the artefact has not necessarily been retrieved recently. Weaker — use for controlled/commercial levels where retrieval is expensive but authorization status is what the gate needs to confirm.
  - **`""`** — default when `verified: false`.
- **`last_reviewed`** is a soft staleness signal. `science-tool health` warns on old values; commands do not block. When `verified: true`, `last_reviewed` MUST be populated.
- **`verified_by`** captures agent identity for audit trails. Format: free text; typical values are `"claude"`, `"keith"`, `"claude+keith"`.
- **`source_url`** is the discovery-level canonical URL, used for verification and first-time retrieval. Execution does NOT read from `source_url` — it reads from resources enumerated in the linked datapackage, or from `local_path` if no datapackage has been materialized.
- **`local_path`** is the optional explicit runtime path when no datapackage is warranted (small single-file sources, one-off reference tables). Mutually exclusive with `datapackage` at runtime; if both are set, `datapackage` wins.
- **`credentials_required`** is empty for `public` and `registration` levels; populated with the specific accession/DAR reference for `controlled` and a license name for `commercial`.
- **`datapackage`** is a relative path to a staged `datapackage.json`. Empty until staging produces one; populated by the staging step. Authoritative for resource-level metadata at runtime.
- **`exception`** is a structured Branch-B record. Populated iff `verified: false` AND the dataset is still consumable by the project under a documented scope-decision. Mutually exclusive with `verified: true`.
  - **`mode: "scope-reduced"`** — this dataset was dropped from the current task's scope; a follow-up task (`followup_task`) will revisit access acquisition.
  - **`mode: "expanded-to-acquire"`** — the current task absorbed the access-acquisition work (submit DAR, wait, revisit); `decision_date` records when the expansion was agreed.
  - **`mode: "substituted"`** — an alternative dataset is being used instead; `superseded_by_dataset` points at the substitute.
  - **`mode: ""`** — no structured exception; the entity is unverified and genuinely not consumable yet. Plans that reference such an entity halt the gate check.

### Lineage: `parent_dataset` and `siblings`

A paper or source with multiple artefacts at different access levels produces multiple entities. `parent_dataset` on each sibling is the **authoritative** link; `siblings:` on the umbrella is an optional cached view that can be regenerated from the children at read time.

```yaml
# doc/datasets/li2021.md (umbrella — narrative only, NOT consumable)
id: "dataset:li2021"
title: "Li 2021 — body map of somatic mutagenesis in normal tissues"
accessions:
  - "EGAD00001007859"
access:
  level: "mixed"
  verified: false           # umbrellas are never `verified: true`; they aren't consumed directly
siblings:                   # OPTIONAL cached view — derivable from children's parent_dataset
  - "dataset:li2021-nature-coding-snvs"
  - "dataset:li2021-ega-wes-fastqs"
```

```yaml
# doc/datasets/li2021-nature-coding-snvs.md (public sibling — consumed by plans)
id: "dataset:li2021-nature-coding-snvs"
title: "Li 2021 Nature Supplementary Table 3 — coding SNVs"
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
  local_path: "data/li2021_somatic_mutations.tsv"   # or a datapackage path
parent_dataset: "dataset:li2021"
```

```yaml
# doc/datasets/li2021-ega-wes-fastqs.md (controlled sibling — scoped out for now)
id: "dataset:li2021-ega-wes-fastqs"
title: "Li 2021 EGA WES FASTQs"
accessions:
  - "EGAD00001007859"
access:
  level: "controlled"
  verified: false
  credentials_required: "EGA DAC EGAC00001002218"
  exception:
    mode: "substituted"
    decision_date: "2026-04-19"
    superseded_by_dataset: "dataset:li2021-nature-coding-snvs"
    rationale: "Coding SNVs from the Nature supplement cover t111's scope; raw WES deferred."
parent_dataset: "dataset:li2021"
```

Plans reference the specific sibling they consume (`dataset:li2021-nature-coding-snvs`), never the umbrella. The umbrella exists for narrative and discovery only and is flagged by the "umbrella cannot be consumed" state invariant if a plan tries to reference it.

Drift between `parent_dataset` (child-side) and `siblings:` (parent-side) is caught by `dataset_invariant_violation` in `science-tool health`. Siblings may be regenerated at any time by scanning children.

### `consumed_by` backlink

Each dataset entity lists the plans that consume it. Populated by `/science:plan-pipeline` in **Step 4.5** (after the plan file is written and its slug is stable), not in Step 2b.

**Canonical consumer identity:**

- **`plan:<plan-file-stem>`** is the canonical backlink. Slug is the plan's markdown filename with date prefix and `.md` extension stripped. Example: `plan:2026-04-18-t111-normal-tissue-spectra-plan`.
- This is deterministic, stable across git history, and unambiguous in both Inquiry and Task modes (Inquiry mode plans still write to a dated `plan:<date>-<inquiry-slug>-plan` file).
- Task and workflow IDs are **optional secondary backlinks** added when available; they are not the gate's identity. Example: `task:t111` or `workflow:extract_normal_tissue_spectra` may accompany `plan:<...>` but do not substitute for it.

```yaml
consumed_by:
  - "plan:2026-04-18-t111-normal-tissue-spectra-plan"   # canonical
  - "task:t111"                                         # secondary, optional
  - "workflow:extract_normal_tissue_spectra"            # secondary, optional
```

**Write timing:**

- Step 2b (gate check) reads `access.verified` and `access.exception` but does NOT mutate `consumed_by`. Halting in Step 2b prevents a stale entity update when the plan never gets written.
- Step 4.5 (new, after plan file is written) appends `plan:<stem>` to each consumed dataset's `consumed_by` list. Deduplicated against existing entries.
- When a plan is renamed or superseded, the old `plan:<...>` entry may be manually removed; health does not enforce removal.

**Format:** list of `<type>:<slug>` entity references. No schema enforcement on entity-type membership in v1; inverse lookups via `science-tool dataset consumers <slug>` parse the list as-is.

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

## State invariants

The schema implies six machine-checkable rules. `science-tool health` surfaces violations as `dataset_invariant_violation` (warning tier; no enforcement in v1 beyond surfacing):

1. **Umbrella entities are not consumable.** An entity with a non-empty `siblings:` list (umbrella) MUST NOT appear in any other entity's `consumed_by` list. Plans consume granular siblings, never umbrellas.
2. **`verified: true` requires method + date.** `access.verified: true` implies `access.verification_method ∈ {"retrieved", "credential-confirmed"}` and `access.last_reviewed` is a non-empty YYYY-MM-DD string.
3. **`verified: true` and `exception.mode` are mutually exclusive.** A verified entity has no exception; an exception only applies to entities that are genuinely unverified but still consumable under a structured Branch-B decision.
4. **`consumed_by` entries are deduplicated** by the full `<type>:<slug>` key. Duplicate writes are no-ops.
5. **Children must agree with parent on lineage.** If entity A has `parent_dataset: B`, then either entity B has A in its `siblings:` list OR entity B has an empty `siblings:` list (cached-view-unmaterialized case). B's `siblings:` listing A without A's `parent_dataset: B` is a violation.
6. **`local_path` and `datapackage` do not both authoritatively drive execution.** Both fields may be populated (`local_path` as a staged single-file escape hatch, `datapackage` as the structured manifest); when both are present `datapackage` wins at runtime. When neither is present on a `verified: true` entity, the entity is effectively "verified-but-not-staged" — legal, but any plan that consumes it must stage before execution.

## Lifecycle

```
Discovery          /science:find-datasets creates doc/datasets/<slug>.md with:
                     access.verified: false
                     access.verification_method: ""
                     access.level: <best-guess from LLM knowledge + repo metadata>
                     consumed_by: []
    ↓
Verification       Manually (log entry) or via future `science-tool dataset verify`:
                     Public:     retrieve source_url → confirm match → flip
                                 verified: true, verification_method: "retrieved"
                                 + last_reviewed + verified_by + log entry
                     Controlled: confirm DAR/DUA → flip verified: true,
                                 verification_method: "credential-confirmed"
                                 + last_reviewed + verified_by + log entry
    ↓
Planning           /science:plan-pipeline §Step 2b (gate check only):
                     resolve each input to dataset:<slug>
                     enforce access.verified: true OR access.exception.mode != ""
                     halt with Branch A/B options if neither
                     (NO mutation of consumed_by at this step)
    ↓
Plan written       /science:plan-pipeline §Step 4 writes the plan file.
                     The plan's stable slug now exists.
    ↓
Backlink           /science:plan-pipeline §Step 4.5:
                     append plan:<plan-file-stem> to consumed_by on each
                     dataset the plan references. Dedupe against existing
                     entries.
    ↓
Execution          Staging / pipeline reads resources via the linked
                     datapackage.json (authoritative). If no datapackage
                     exists, execution reads from access.local_path as an
                     explicit single-file escape hatch, OR stages first to
                     produce a datapackage. Execution never reads directly
                     from source_url.
    ↓
Review             /science:review-pipeline Dim 3:
                     verify every input resolved to a dataset entity
                     verify access.verified: true OR exception.mode != ""
                     verify consumed_by contains plan:<plan-file-stem>
                     verify state invariants hold
                     WARN if last_reviewed is stale (> 12 months)
```

### Task-mode example

`/science:plan-pipeline` in Task mode (no formal inquiry) for a task like cbioportal's t111:

1. **Input to plan-pipeline:** task ID `t111` or a free-text task description.
2. **Step 2 (identify computational requirements):** the planner enumerates inputs: Li 2021 normal-tissue mutation calls; a UBERON mapping table.
3. **Step 2b (gate check):**
   - `dataset:li2021-nature-coding-snvs` exists with `access.verified: true` (verified 2026-04-19, method `retrieved`) → PASS.
   - `dataset:xu2025-ega-wes-somatic-calls` exists with `access.verified: false` and no `exception.mode`. Planner halts with:
     > "Branch B: `dataset:xu2025-ega-wes-somatic-calls` is dbGaP-only (`access.credentials_required: 'dbGaP phs000424.v7 DAR'`). Choose: (a) scope-reduce and defer to a follow-up task; (b) expand the current task to include DAR submission; (c) substitute an alternative dataset."
   - User selects (a). Planner writes `access.exception: {mode: "scope-reduced", decision_date: "2026-04-19", followup_task: "task:t112", rationale: "Li2021 public supplement covers t111's scope; raw WES deferred."}` to `dataset:xu2025-ega-wes-somatic-calls` and appends a verification-log entry. Re-runs the gate; the entity now passes (exception is populated).
4. **Step 3 (add computational nodes):** skipped in Task mode.
5. **Step 4 (write plan):** file written at `doc/plans/2026-04-18-t111-normal-tissue-spectra-plan.md`. Canonical plan identity is `plan:2026-04-18-t111-normal-tissue-spectra-plan`.
6. **Step 4.5 (backlink write):** `plan:2026-04-18-t111-normal-tissue-spectra-plan` appended to `dataset:li2021-nature-coding-snvs.consumed_by` (deduplicated) and `dataset:xu2025-ega-wes-somatic-calls.consumed_by`. (The latter tracks scope-reduced consumers too, so the follow-up task can find them.)
7. **Step 5 (inquiry-status update):** skipped in Task mode.

The key property: in Task mode there's no inquiry slug, but the plan's filename produces a stable, deterministic backlink. Review-pipeline later checks that this exact `plan:<stem>` appears in each referenced dataset's `consumed_by`.

## Command integrations

### `/science:find-datasets`

- Emit one dataset entity per distinguishable artefact at a distinct access level. A paper with one public supplement and one controlled EGA deposit produces two entities plus optionally a third umbrella entity linking them via `parent_dataset` / `siblings`.
- New entities start with `access.verified: false`, `access.last_reviewed: ""`, `consumed_by: []`.
- Populate `access.level`, `access.source_url`, and `access.credentials_required` from discovery evidence. When uncertain, use the most restrictive known level; the verification step corrects.

### `/science:plan-pipeline` — new Step 2b: Data-access gate + Step 4.5: Backlink write

Step 2b is inserted between the existing Step 2 (identify computational requirements) and Step 3 (add computational nodes to the inquiry). Runs in both Inquiry and Task modes. **Step 2b does not mutate the dataset entity's `consumed_by` list** — that happens in Step 4.5, after the plan file is written.

```markdown
### Step 2b: Data-access gate (both modes)

For each input data source identified in Step 2:

1. Resolve to a `dataset:<slug>` entity. If no entity exists, invoke
   `/science:find-datasets` to create one. Do not proceed with a URL alone.
2. Check the gate:
   - If `access.verified: true` → PASS, continue.
   - If `access.verified: false` AND `access.exception.mode` is non-empty → PASS
     (structured Branch-B decision already exists).
   - Otherwise → HALT and raise to the user:
     - **Branch A**: verifiable under current credentials — run verification
       (manual or future `science-tool dataset verify`), then re-run this step.
     - **Branch B**: requires credentials the project does not hold. Three options:
       (a) scope-reduce: defer this source to a follow-up task; populate
           `access.exception` with `mode: "scope-reduced"`, `decision_date`,
           `followup_task`.
       (b) expand: add credential acquisition to the current task; populate
           `access.exception` with `mode: "expanded-to-acquire"`, `decision_date`.
       (c) substitute: pick an alternative dataset; populate
           `access.exception` with `mode: "substituted"`,
           `superseded_by_dataset: "dataset:<alternative>"`.
     After writing the structured exception + a prose log entry, re-run the gate;
     the entity now passes.
3. Do NOT mutate `consumed_by` here. The backlink write is Step 4.5, after the
   plan file exists.
```

Step 4.5 is inserted between Step 4 (write the implementation plan) and Step 5 (update inquiry status). Runs in both modes.

```markdown
### Step 4.5: Register plan with consumed datasets (both modes)

The plan file now exists at a known path. Compute `plan:<plan-file-stem>` from
the filename (strip directory and `.md` extension).

For each dataset entity referenced in Step 2b, append `plan:<plan-file-stem>` to
`consumed_by`, deduplicated against existing entries. Also append any secondary
backlinks the planner has in scope (`task:<id>` if a task is being tracked;
`workflow:<slug>` if a new workflow is being registered). Do not rewrite
existing entries.

Append a short log entry to each dataset entity's verification log:
  "<YYYY-MM-DD> (<agent>): consumed by plan:<plan-file-stem>"
```

### `/science:review-pipeline` Dim 3 upgrade

Existing Dim 3 ("Data Availability") replaced with the entity-resolution check, now reading structured exception state rather than parsing prose:

```markdown
#### Dimension 3: Data Availability

For each input data source (every `BoundaryIn` node or data-acquisition step in the plan):

- Does it resolve to a `dataset:<slug>` entity in `doc/datasets/`?
- Is the entity consumable under the gate rule? (`access.verified: true`
  OR `access.exception.mode ∈ {"scope-reduced", "expanded-to-acquire", "substituted"}`)
- Is `access.source_url` populated? (Discovery URL, not per-resource URLs.)
- Does the entity's `consumed_by` list include `plan:<this-plan-file-stem>`?
- Is `access.last_reviewed` within the last 12 months (when `verified: true`)?
- Do all state invariants hold for the entity? (See §State invariants.)

**Scoring:**

- **PASS** — all sources resolve; all pass the gate rule; `consumed_by` lists `plan:<stem>`;
  `last_reviewed` fresh when applicable; state invariants hold.
- **WARN** — at least one of: stale `last_reviewed` (> 12 months); `consumed_by` missing the
  canonical `plan:<stem>` backlink; incomplete metadata (missing `source_url` on a verified
  entity, no verification-log entry); state-invariant warning (e.g., lineage drift).
- **FAIL** — any of:
  - A source does not resolve to a dataset entity.
  - A source is `access.verified: false` with `access.exception.mode: ""` (no structured
    Branch-B decision).
  - A source has `access.verified: true` but `access.verification_method: ""` or no
    `last_reviewed` (invariant violation).
  - A plan references an umbrella (an entity with non-empty `siblings:`).
  - A source has `access.verified: true` AND a non-empty `access.exception.mode` (mutual-
    exclusivity invariant).
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

`science-tool health` grows five anomaly classes tied to the new schema:

| Anomaly | Severity | Trigger |
|---|---|---|
| `dataset_consumed_but_unverified` | error | entity has `consumed_by: [...]` non-empty but `access.verified: false` AND `access.exception.mode: ""` (structured exception absent) |
| `dataset_stale_review` | warning | entity has `access.verified: true` but `last_reviewed` older than 12 months (configurable) |
| `dataset_missing_source_url` | warning | entity has `access.verified: true` but `access.source_url: ""` |
| `dataset_datapackage_drift` | warning | entity's cached `formats`/`size_estimate` differs from its linked `datapackage.json` |
| `dataset_invariant_violation` | warning | any of the six state invariants is false — e.g., umbrella in another entity's `consumed_by`; `verified: true` without `verification_method`; `verified: true` AND non-empty `exception.mode`; asymmetric lineage |

The `dataset_consumed_but_unverified` anomaly is the strongest signal that a plan is about to fail at execution time; it fires whenever a pipeline references a dataset the project hasn't actually confirmed access to AND hasn't documented a structured scope decision for.

## Template Updates

Replace `templates/dataset.md` with the extended version described in the Data Model section above. Parsing is backward-compatible through two rules:

1. **Flat `access: <level>` shorthand.** Existing entries with `access: public|controlled|mixed` (scalar) parse as `access.level = <value>` with all other `access.*` subfields defaulting (`verified: false`, `verification_method: ""`, etc.). Entities that have never been verified continue to look like they were; the gate check fails them until migrated.
2. **`datasets:` field alias.** Existing entries that use `datasets: [...]` continue to parse as `accessions: [...]`. The `datasets:` name is soft-deprecated; tooling reads either but writes the new name. Bulk renaming is not required.

Migration is opt-in per entity — no bulk rewrite. When a plan is drafted against an un-migrated dataset entity, `/science:plan-pipeline` §Step 2b halts because `access.verified: false` and `access.exception.mode: ""`, which prompts the user to either run verification (moving the entity to the new schema) or write a structured exception.

### Migration example

**Before (legacy entity):**

```yaml
---
id: "dataset:li2021"
type: "dataset"
title: "Li 2021 body map of somatic mutagenesis in normal tissues"
status: "active"
tier: "use-now"
access: "mixed"                           # flat scalar
license: "CC-BY-4.0"
datasets:                                 # old field name
  - "EGAD00001007859"
ontology_terms: []
source_refs:
  - "cite:Li2021"
created: "2026-04-18"
updated: "2026-04-18"
---
```

**After (structured, post-migration):**

```yaml
---
id: "dataset:li2021"
type: "dataset"
title: "Li 2021 body map of somatic mutagenesis in normal tissues"
status: "active"
tier: "use-now"
license: "CC-BY-4.0"
accessions:                               # renamed from `datasets:`
  - "EGAD00001007859"
ontology_terms: []
access:
  level: "mixed"                          # moved under structured block
  verified: false                         # umbrellas are never verified
  verification_method: ""
  last_reviewed: ""
  source_url: ""
  credentials_required: ""
  datapackage: ""
  local_path: ""
  exception:
    mode: ""
    decision_date: ""
    followup_task: ""
    superseded_by_dataset: ""
    rationale: ""
siblings:
  - "dataset:li2021-nature-coding-snvs"   # populated by granularity split
  - "dataset:li2021-ega-wes-fastqs"
parent_dataset: ""
consumed_by: []
source_refs:
  - "cite:Li2021"
related: []
created: "2026-04-18"
updated: "2026-04-19"
---
```

Migration here is two manual moves: (a) flat `access:` → structured `access.level`; (b) `datasets:` → `accessions:`. A one-off `science-tool dataset migrate <slug>` helper could automate this but is not required for v1 — tooling reads both shapes.

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

- **Granularity: one entity per artefact.** A paper with a public supplement and a controlled raw-read deposit produces separate entities linked via `parent_dataset` (authoritative) / `siblings` (optional cached view on the umbrella).
- **Staleness: `last_reviewed` only; no automatic expiry enforcement.** v1 surfaces stale reviews as warnings in health and review-pipeline; it does not block pipelines on stale reviews.
- **Data-package relationship: reference, not duplicate.** Resource-level metadata (SHA256s, paths, schemas, sizes) lives in `datapackage.json`. Cached entity-level fields are advisory once a datapackage exists.
- **Gate record location: on the dataset entity.** No separate `doc/plans/<slug>-data-gate-record.md` artefact.
- **`verified: true` requires `verification_method`.** Distinguishing `"retrieved"` (artefact pulled and matched expectations) from `"credential-confirmed"` (authorization exists but retrieval not recent) keeps the gate honest for controlled/commercial datasets.
- **Branch-B decisions are structured.** `access.exception: { mode, decision_date, followup_task, superseded_by_dataset, rationale }` is the machine-readable form; the prose log remains the human narrative. Dim 3 and health anomalies read the structured form.
- **`consumed_by` uses `plan:<plan-file-stem>` as canonical identity.** Task and workflow IDs are optional secondary backlinks. The backlink is written in a new Step 4.5 (after the plan file exists), not in Step 2b.
- **Execution reads from the datapackage, not `source_url`.** `source_url` is for verification + first-time retrieval; runtime consumes datapackage resources (or `local_path` as a single-file escape hatch).
- **`datasets:` → `accessions:` rename.** The old field name read confusingly on a dataset entity. New tooling writes `accessions:`; legacy entries still parse via read-time alias.
- **Umbrella entities are not consumable.** Plans reference granular siblings; umbrellas exist for narrative and discovery only. Enforced by a state invariant.
- **Verification automation: deferred.** v1 is structural-only. `science-tool dataset verify` is documented but not implemented.

## Follow-on Work

- **`science-tool dataset verify <slug>` CLI.** Automates the flip for public URLs (retrieve → SHA256 → flip `verified: true` with `verification_method: "retrieved"` → append log). Interactive prompt for controlled sources (records `credential-confirmed`). Deferred because v1's structural change is independently valuable and the automation surface benefits from seeing real-world usage patterns first.
- **`science-tool dataset migrate <slug>` CLI.** Rewrites legacy flat `access: <level>` and `datasets: [...]` fields into the structured schema. Idempotent; safe to run in bulk when a project decides to migrate all entities at once.
- **`last_reviewed` expiry enforcement.** If stale-review warnings go unactioned in practice, consider upgrading them to errors with a configurable threshold. Not required until data accumulates on whether 12 months is the right default.
- **Shared cross-project dataset catalogue.** When multiple projects reference the same Li 2021 supplementary table, duplicating the entity is wasteful. A framework-level shared catalogue (perhaps under `~/d/science/data/datasets/`) would let projects inherit and layer project-specific `consumed_by` onto a canonical entity. Non-trivial; defer.
- **Graph-layer representation of `consumed_by`.** If a future query consumer wants to traverse "plan → dataset → dataset's verification log" in the knowledge graph, the backlink will need a graph edge (e.g., `sci:consumesDataset`). Frontmatter-only is sufficient for v1.
- **Datapackage drift reconciliation command.** When the dataset entity's cached `formats` / `size_estimate` drift from the linked datapackage, `science-tool dataset reconcile <slug>` could rewrite the entity's cached fields from the datapackage. Deferred until drift is observed in practice.
- **Dataset entity generation from datapackage.** For projects that receive a datapackage from an upstream collaborator, a `science-tool dataset from-datapackage <path>` command could emit a dataset entity stub with access metadata. Natural fit but not required by v1.
- **`science-tool dataset siblings regenerate <parent-slug>`.** Recomputes an umbrella entity's `siblings:` list from any children that point at it via `parent_dataset`. Makes the cached view trivially re-derivable; addresses the "drift" case for the state invariant.
- **Cross-plan consumption weights.** Currently `consumed_by` is an unordered list. A richer form could record *which part* of each plan consumes the dataset (single transformation, ancillary lookup, validation only), enabling impact queries like "if this dataset moves access level, which plans are affected as primary vs tangential?". Not required by v1.
