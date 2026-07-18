# Datasets

Datasets are reference-class entity owners with a rich lifecycle. This chapter
covers how papers use them, how gene-set collections are modeled, how external
and derived datasets are scoped and verified, their runtime state and QA, and
how bulk payload is kept out of version control. See [Entities](entities.md) for
the shared entity shape, fields, and source-entity CLI that all kinds — datasets
included — build on.

## Paper Dataset Usage

Papers should express dataset dependence with `dataset_usage` entries. The
retired paper `datasets` field is not materialized. Validation reports it as an
error; rewrite any remaining paper `datasets` values to explicit
`dataset_usage` entries before building the graph.

## Gene-Set Collections And Members

Gene-set collections are normal `dataset` entities with the
`bio.geneset/1.0` extension. The collection frontmatter declares the member row
resource, row counts, set-size summary, and the `identifier_space` used by the
member identifiers. The member table is keyed by `set_key` and may carry
per-set `dataset_usage`, source PMIDs, and source-class overrides.

Most sets stay as rows in the collection. Promote an individual set only when it
needs its own evidence-bearing reference, independent provenance, or review
state. A promoted set is a child `dataset` with
`bio.geneset.member/1.0`, `origin: derived`, `datapackage: virtual:member-of`,
and `derivation.kind: member_of` pointing back to the parent collection:

```yaml
schema_profile: science-entity-base/1.0+dataset/1.0+bio.geneset.member/1.0
id: dataset:reactome-r-hsa-1
kind: dataset
origin: derived
source_class: reference
parent_dataset: dataset:reactome-v89
datapackage: virtual:member-of
derivation:
  kind: member_of
  parent_dataset: dataset:reactome-v89
  member_key: R-HSA-1
identifier_space:
  tier: gene
  namespace: hgnc_id
n_members: 42
```

The virtual payload resolver slices the parent collection's `members_resource`
by `derivation.member_key` and returns that row plus the collection's
`identifier_space`. No tiny per-set data artifact is required unless a workflow
explicitly materializes one.

Use `science commons member-payload dataset:<member> --json` to inspect the
resolved virtual payload for a promoted member dataset. The command uses the
shared `member_of` dispatcher and supports both `bio.geneset.member` and
`bio.reference_graph.member` datasets.

For reference graphs, use
`science commons reference-graph scaffold-member <parent_dataset> <member_key> --slug <slug>`
to preview a promoted `bio.reference_graph.member` child dataset. Dry-run is
the default; add `--apply` to write the child `entity.md` plus the virtual
`datapackage.yaml` sibling.

Use `science commons reference-graph resolve-member <registry_id> <member_key> --json`
to resolve an exact graph member key from a pinned reference graph node index.
Deprecated or withdrawn members are returned with lifecycle state and
`replaced_by`; replacements are not followed automatically.

## Dataset Lifecycle

`dataset` is the single entity kind for data that a project consumes, whether
the data comes from an external source or from a workflow run. Dataset owners
live under `entities/datasets/` in layout v3 projects. The entity frontmatter is
the authority for project-level metadata; a runtime `datapackage.yaml` or
`datapackage.json` is the authority for resource-level file metadata.

The split is intentional:

| Surface | Owns |
|---|---|
| Dataset entity | `id`, `kind`, `title`, `status`, `origin`, `dataset_class`, `tier`, `license`, `update_cadence`, `ontology_terms`, `access`, `derivation`, lineage, `qa_report`, `consumed_by`, and human prose. |
| Runtime datapackage | Resource names, paths, hashes, byte counts, formats, schemas, and other file-level package details. |

Dataset entities use `profiles: ["science-pkg-entity-1.0"]`. Do not put
`resources:` on the entity; consumers that need resource details read the file
named by `datapackage:`.

### Biological Identity Context

For biological datasets, the dataset entity's `identity_context` block is the
source of truth for organism, assembly, and molecular identifier scope. A
runtime datapackage may carry a derived `science.identity_context` stamp for
portable validation, but that stamp is read-only from the author's perspective.
When present, validation treats disagreement between the datapackage stamp and
the dataset entity as an error.

Mandatoryness is profile-scoped:

| Dataset shape | Required identity context |
|---|---|
| Coordinate assays | `taxon` plus `assembly`. |
| Gene-bearing datasets | `taxon` plus the relevant `molecular_ids.gene` tier. |
| Protein-bearing datasets | `taxon` plus the relevant `molecular_ids.protein` tier. |
| Variant-bearing datasets | `taxon` plus the relevant `molecular_ids.variant` tier, and `assembly` when variants are coordinate-anchored. |
| Non-bio or base-profile datasets | Exempt unless a bio profile is declared. |

Use an NCBI taxid integer directly as `taxon`, for example `taxon: 9606`. Use
dataset refs for pinned registries and crosswalks, such as
`dataset:assembly-registry` for assembly digests or
`dataset:gene-crosswalk-hgnc` for HGNC gene identifiers.

`declared_unresolved` is the honest declaration-level state: the author knows
which tier or namespace applies, but the exact digest or canonical mapping is
not resolved yet. For assembly, use `seqcol_digest: UNKNOWN` with
`resolution_status: declared_unresolved` when the digest is not resolved. For
molecular tiers, declare the `namespace`, optional `registry`, and
`resolution_status` without adding unknown-value fields. Full resolution belongs
at a later resolver or publish boundary; do not invent placeholder digests to
make an in-progress dataset look resolved.

Planning and acquisition gates require the declaration for identity-bearing
inputs, not necessarily full resolution. Coordinate and bio identity-bearing
profiles must declare `taxon` plus the relevant assembly or molecular tier, or
explicitly carry UNKNOWN/unresolved where resolution is pending.

### Origin

Every dataset has an `origin`:

- `external` means the dataset comes from a paper, public repository, portal,
  controlled-access archive, commercial source, or another source outside the
  local workflow run.
- `derived` means the dataset is a logical output of a recorded workflow run.

External datasets carry an `access:` block. Derived datasets carry a
`derivation:` block. Do not mix the two on one entity.

### Dataset Class

`dataset_class` describes how the record can be used:

| Class | Meaning |
|---|---|
| `deposit` | Obtainable data that can be staged as a local runtime artifact. |
| `reference` | A portal, registry, atlas, leaderboard, or other lookup source that should be tracked but normally has no local runtime artifact. |
| `pointer` | A record worth tracking for planning or discovery, but not directly usable as staged data yet. |

`dataset_class` is independent from `source_class`. A reference genome can be a
downloadable `deposit`; a web portal can be a `reference`.

### External Datasets

Create new external candidates with:

```bash
science dataset add <slug> --title "<title>"
```

`science dataset add` writes a local `entities/datasets/<slug>.md` candidate
with `origin: external`, `dataset_class: deposit` by default, `license:
unknown`, and an unverified `access:` block. Use `--class reference` or
`--class pointer` when the record is not a staged-data deposit. Reference and
pointer records need an `access.source_url`.

When access has been checked, record the whole coupled edit with:

```bash
science dataset verify-access <slug> --license <spdx-or-sentinel> --method <method>
```

For deposits, valid verification methods are `retrieved`,
`credential-confirmed`, and `landing-confirmed`. For reference records, use `credential-confirmed`,
`landing-confirmed`, or `metadata-confirmed`. For pointer records, use
`landing-confirmed` or `metadata-confirmed`.

If an external dataset cannot be used as originally scoped, record a structured
exception instead of leaving `access.verified: false` unexplained:

```bash
science dataset verify-access <slug> --license <spdx-or-sentinel> \
  --exception scope-reduced --rationale "<why>"
```

Exception modes are `scope-reduced`, `expanded-to-acquire`, and `substituted`.
The command updates the frontmatter and appends a dated entry under
`## Access verification log`.

#### Reproducibility (`access.reproducibility`)

`access.level` says *how gated the source is*; `access.reproducibility` says *whether an
independent third party can regenerate the analysis*. Three controls, mapped to the
[Five Safes](https://fivesafes.org/):

- `obtainability` — safe people/projects (who can get in).
- `execution` — safe setting (where compute runs).
- `extractability` — safe outputs (what can leave).

The **class** is derived, never stored: `third-party-reproducible` > `credentialed-reproducible`
> `trust-based-output` > `insider-only`; `unknown` is unassessed (not "low"). Worked examples:

| Dataset shape | obtainability / execution / extractability | class |
|---|---|---|
| Public GEO download | public / local / full-dataset | third-party-reproducible |
| Self-serve DUA extract | self-service-dua / local / analysis-dataset | credentialed-reproducible |
| N3C / OpenSAFELY enclave | approved-project / trusted-environment / aggregate-reviewed | trust-based-output |

A transparency-bound project sets `reproducibility_policy` in `science.yaml`; a plan may lower the
bar or waive one dataset explicitly (dated, scoped, with rationale + mitigation).

### Derived Datasets

Derived dataset entities are machine-authored from workflow runs. A workflow
declares logical outputs in `entities/workflows/<slug>.md`:

```yaml
outputs:
  - slug: "<output-slug>"
    title: "<Output title>"
    resource_names: ["<frictionless-resource-name>"]
    identity: {}
    ontology_terms: []
```

For identity-bearing outputs, `outputs[].identity` is the workflow contract,
colocated with `resource_names`. It may inherit or transform input identity, but
it is the authority that `science dataset register-run` reads; an optional
output `identity_context.yaml` sidecar is assertion-only and must agree with the
contract.

#### Output Support Cardinality

For aggregate outputs, `outputs[].support` declares the minimum number of
distinct contributors required before a derived datapackage is trustworthy. The
field is opt-in: `science validate` evaluates support cardinality only for
workflow outputs that declare `support`, independent of strict mode and without
nudging undeclared outputs.

```yaml
outputs:
  - slug: os-summary
    title: "Overall survival summary"
    resource_names: ["os_summary"]
    support:
      unit: dataset
      min: 3
      expected: 5
```

`support.unit` is one of `dataset`, `cohort`, `sample`, or `source`. `min` is
the hard floor and must be at least 1. `expected` is optional, must be at least
`min`, and records the soft target for a well-supported aggregate.

Support moves through a two-hop handoff:

1. The workflow producer stamps each run-aggregate resource with
   `science.support: {unit, observed}` in the runtime datapackage. `observed`
   is the number of distinct contributing units wired into that aggregation,
   not `max(num_present)` or another row-level completeness statistic.
2. `science dataset register-run` reduces all resources in an opted-in output
   to per-output datapackage `science.support` by taking the minimum observed
   value across the listed resources.

Every resource listed in an opted-in output must stamp support. This is a
fail-closed rule for multi-resource outputs: if any listed resource is unstamped,
registration records the per-output support as `observed: null`, and validation
reports the missing stamp. Put ancillary non-aggregating resources in a separate
non-opted-in output when they cannot meaningfully stamp support.

Malformed producer-stamped `observed` values are preserved for diagnosis rather
than silently repaired; validation reports them as malformed support stamps.

Support gate results are:

| Code | Severity | Meaning |
|---|---|---|
| `aggregation-support.stamp-missing` | ERROR | An opted-in output includes at least one resource without `science.support`; validation exits 1. |
| `aggregation-support.malformed-stamp` | ERROR | A producer-stamped `observed` value is malformed; validation exits 1. |
| `aggregation-support.unit-mismatch` | ERROR | The declared support unit differs from a stamped resource unit; validation exits 1. |
| `aggregation-support.below-floor` | ERROR | Observed support is below `min`; validation exits 1. |
| `aggregation-support.below-expected` | WARN | Observed support is at or above `min` but below `expected`. |

For example, an overall-survival output with `support: {unit: dataset, min: 3,
expected: 5}` that stamps a run aggregate with `observed: 1` fails validation
with `aggregation-support.below-floor` at ERROR severity. This catches the MM30
style `k=1` collapse: a summary produced from one contributing dataset cannot
pass a floor that requires at least three datasets, even if its rows contain
many present values.

A completed workflow run lives under `entities/workflow-runs/` and lists its
upstream dataset inputs. After the run writes its aggregate runtime
datapackage, register the derived outputs with:

```bash
science dataset register-run workflow-run:<slug>
```

Registration writes one per-output `datapackage.yaml` under the run results
tree, creates one `origin: derived` dataset entity per declared workflow output,
propagates output identity to the derived entity's `identity_context`, writes
the derived datapackage stamp, and updates symmetric edges:

- the workflow run's `produces:` lists each derived dataset;
- each upstream dataset's `consumed_by:` includes the workflow run.

Per-output datapackages are views into the run output, not relocated copies of
the resources. In derived lineage, `proxy.sources[].dataset` entries are data
ancestors recorded in `derivation.inputs`; `transform.dataset` and `proxy.via`
entries are reference artifacts recorded in `derivation.transformations[]`.

### Runtime State And Inspection

Use the singular `science dataset` command group for the catalog lifecycle:

```bash
science dataset list
science dataset list --origin external --unverified
science dataset list --include-gated
science dataset show <slug>
science dataset consumers <slug>
science dataset prioritize --explain
science dataset reconcile <slug>
```

`science dataset list` hides gated external deposits by default; pass
`--include-gated` or a specific `--level` to inspect them. `science dataset
prioritize` ranks records by accessibility, runtime state, and graph reach. It
excludes gated deposits, references, and pointers by default so the first view is
actionable.

Runtime state is derived from the entity:

| State | Meaning |
|---|---|
| `runnable` | A `datapackage` or `local_path` is present. |
| `unstaged-deposit` | Access is verified but a deposit has not been staged yet. |
| `blocked-access` | Access is gated, unverified, or exception-gated. |
| `reference-only` | The record is a reference-class dataset. |
| `pointer-only` | The record is a pointer-class dataset. |

### Prioritization And Reach

`science dataset prioritize` ranks local dataset records as:

```text
readiness_weight * (1 + reach) * leverage_tilt
```

Readiness comes from the dataset entity's access, origin, derivation, and
runtime pointer state. Reach is the number of question or hypothesis targets the
dataset connects to. Leverage tilt is available when a fresh graph is loaded and
uses proposition summary signals such as contested, single-source, no-empirical,
and risk score.

Reach is intentionally authorable without a graph, then enriched by the graph:

| Surface | Meaning for reach |
|---|---|
| Dataset `related:` | Dataset lists a `question:*` or `hypothesis:*` it informs. |
| Q/H `related:` | A question or hypothesis lists a `dataset:*` back-edge. |
| Q/H `datasets:` | A question or hypothesis directly names needed or relevant datasets. |
| Consumer `dataset_usage` plus `related:` | A paper or other consumer names datasets and is related to Q/H records. |
| Evidence-line `dataset_usage` plus proposition reach | An evidence line uses a dataset and supports/disputes a proposition that reaches Q/H records. |

These paths are a union. Do not duplicate edges only to satisfy prioritization:
use Q/H `datasets:` for direct dataset needs, dataset `related:` when the
dataset file is the active editing surface, and `dataset_usage` where a paper,
evidence line, workflow-derived row, or virtual row records actual use.

`science dataset prioritize --coverage --format json` inverts the view to one
row per question or hypothesis. Coverage states are `covered-runnable`,
`covered-unstaged`, `covered-reference`, `covered-pointer`, `blocked-access`,
`unverified`, `missing-required-capabilities`,
`missing-provided-capabilities`, `capability-mismatch`, `out-of-molecular-scope`,
and `no-candidate`.
Gap reasons include `unstaged-deposit`, `only-reference`, `only-pointer`,
`only-gated`, `only-unverified`, `missing-required-capabilities`,
`missing-provided-capabilities`, `capability-mismatch`, and `no-candidate`.

Capability fields keep topical reach separate from evidence fit. A question or
hypothesis that names datasets should declare the data capability it needs:

```yaml
required_capabilities:
  - assay: gene-expression
    modality: bulk-rna
```

A dataset that reaches questions or hypotheses should declare what it can
provide:

```yaml
provided_capabilities:
  - assay: gene-expression
    modality: bulk-rna
  - assay: chromatin-accessibility
    modality: scATAC
```

Within one capability set, all key/value pairs must match. Across sets, any one
matching set is enough. A dataset linked to a target still appears in
`datasets`, but only compatible datasets appear in `compatible_datasets` and
contribute runtime-state coverage credit. `science validate` warns when
capability-relevant targets or datasets omit these fields, or when the fields
are not non-empty lists of non-empty string mappings.

Some entities are non-molecular by nature and legitimately declare no
capabilities — clinical-only cohorts, outcome/registry data, or method/census
questions. Mark these with `capability_scope` so the missing-capability warning is
suppressed instead of firing on an intentional gap:

```yaml
capability_scope: clinical-outcome
```

`capability_scope` means "this entity is outside the molecular assay/modality
gate." Values are `reference-substrate`, `derived-product`, `methodological`,
`model-system` (terminal — the entity measures nothing on any axis) and
`clinical-outcome`, `epidemiological`, `behavioral-instrument` (transitional —
non-molecular measurement, pending a future outcome axis). A scoped target reports
coverage state `out-of-molecular-scope` rather than a capability gap. The field is
mutually exclusive with any non-empty `provided_capabilities` /
`required_capabilities`; declaring both, or using an unknown value, is a
`science validate` warning. A scoped entity never receives molecular coverage
credit.

Treat a flood of `no-candidate` rows as a curation-design signal, not only as a
filtering problem. Especially when the missing rows are internal,
methodological, or too abstract for dataset discovery, the likely follow-up is
to reformulate the upstream question or hypothesis into dataset-addressable
needs before tuning the scan output.

### Typed Resource Schemas

Runtime datapackages can give each tabular resource a typed Frictionless Table
Schema. Science treats that schema as the single source of truth for resource
shape and machine-checkable QA inputs:

```yaml
resources:
  - name: observations
    path: observations.parquet
    schema:
      fields:
        - name: sample_id
          type: string
          constraints: {required: true, unique: true}
        - name: value
          type: number
          constraints: {minimum: 0}
          qa: {low_variance: true, zero_fraction: true}
      primaryKey: sample_id
      missingValues: ["", "NA"]
      qa:
        exclusive_flags: [[case, control]]
```

Native Table Schema declarations are invariants: field `type`,
`constraints.required`, `constraints.unique`, `primaryKey`, `uniqueKeys`,
`foreignKeys`, bounds, enums, and `missingValues` describe data that must be
true. The Science `qa:` extension is deliberately small and distribution
oriented: field-level `low_variance` and `zero_fraction`, plus table-level
`exclusive_flags`.

The schema profile is model-owned in `science_tool.datasets.schema`; the
committed JSON Schema is generated from those Pydantic models rather than
hand-maintained. `science datasets validate --path <datapackage>` checks a
descriptor or package directory through that profile, confirms resource files
exist, and checks declared tabular `schema.fields[]` against the observed table
names and coarse types. A descriptor that is missing, malformed, empty, stale,
or points at absent data fails early instead of warning-and-passing.

Use `science datasets infer-schema` to bootstrap the names-and-types portion of
a resource schema from an existing table:

```bash
science datasets infer-schema <datapackage-dir-or-file> --resource <name>
science datasets infer-schema <datapackage-dir-or-file> --resource <name> --write
science datasets infer-schema <datapackage-dir-or-file> --resource <name> --emit-suggestions suggestions.yaml
science datasets infer-schema <datapackage-dir-or-file> --resource <name> --format json
```

The command is read-only by default. It resolves resources by name first and by
path second, refuses ambiguous matches, reads Parquet types from Arrow metadata,
and samples CSV/TSV resources for coarse type inference. With `--write`, it
applies only safe `fields[].name` and `fields[].type` edits, preserves authored
constraints and QA metadata, refuses authored type conflicts, validates the
whole package before writing, and atomically re-renders the descriptor in its
own JSON/YAML format. It never writes constraints, keys, foreign keys, or
`qa:` declarations; those appear only as human review recommendations.

### Dataset QA

Use the plural `science datasets qa` command for package-level, schema-driven
QA over tabular resources:

```bash
science datasets qa <datapackage-dir-or-file>
science datasets qa <datapackage-dir-or-file> --resource <name>
science datasets qa <datapackage-dir-or-file> --report-dir <dir>
science datasets qa <datapackage-dir-or-file> --config <runknobs.yaml>
science datasets qa <datapackage-dir-or-file> --format json
science datasets qa <datapackage-dir-or-file> --no-strict
```

The command accepts a package directory or a descriptor named
`datapackage.json`, `datapackage.yaml`, or `datapackage.yml`. With
`--report-dir`, it persists `qa_report.json`, `qa_report.md`, and per-resource
report subdirectories. Text output renders one non-`not-applicable` resource
line followed by a package summary. Resource outcomes are `ok`, `fail`,
`blocked`, `skipped`, or `not-applicable`: non-tabular resources are
not-applicable, tabular resources without schemas are skipped, missing data
files are blocked, and evaluated resources fail when any structural QA flag is
emitted.

The QA runner compiles each resource's typed schema into the generic `tabular`
program unless run-knobs select another program. Schema-derived invariants
compile to structural checks: required fields, unique keys, expected types,
hard bounds, enums, missing sentinels, and single-column foreign-key
categoricals. Composite foreign keys are rejected rather than weakened to
per-column checks. A run-knobs file passed with `--config` overlays operational
settings such as soft ranges, polarity, project-local checks, aspect
parameters, and program choice; contract fields are merged with schema-derived
values so authors can tighten a specific run without forking the descriptor.

Exit codes are:

| Code | Meaning |
|---|---|
| `0` | No build-fatal structural package failure, or `--no-strict` was used for local inspection. |
| `1` | A structural package failure fired and strict mode is active. |
| `2` | Bad input, such as missing descriptor, unknown resource, unreadable data, or compile/runner error. |

To feed QA into graph and belief behavior, set a dataset entity's `qa_report` to
the project-root-relative path of the persisted `qa_report.json`. Graph build
does not rerun QA. It reads each opted-in report, requires
`package_structural_failed` to be a JSON boolean, hashes the report, and emits:

- `sci:qaStructuralFailed`
- `sci:qaReport`
- `sci:qaReportHash`
- `sci:qaFailedResource` for failed resources

For empirical evidence lines that rest on structurally failed dependence
datasets, graph build also emits `sci:qaFailedDataset`. Belief aggregation uses
that provenance to apply the QA dataset ceiling; QA-clean support can still
carry the belief if it is sufficient without the failed dataset.

### Sub-Cohort Lineage

Datasets can declare cohort lineage with `parent_dataset` and optional
`siblings`. Graph build materializes `parent_dataset` as a child-to-parent
`sci:subCohortOf` edge. Dataset-derived independence uses that lineage when
deciding whether two empirical evidence lines are truly independent.

When two full-overlap dependence uses refer to the same dataset or an
ancestor/descendant pair in the same lineage, Science emits a commitment:
`DatasetIndependenceCommitment`, `shared-source`, and a
`dataset-derived:*` independence group. Sibling sub-cohorts under the same root
are not committed as the same source; they remain candidate warnings because
they may overlap but are not guaranteed to be duplicate evidence. Partial,
unknown, validation-only, citation-only, indirect, and virtual-row paths also
stay candidate-level.

`science dataset reconcile` checks the narrow duplication channel between the
entity and runtime package: `license`, `update_cadence`, and
`ontology_terms`. Per-resource fields are not reconciled because they belong to
the runtime package only.

### Validation Expectations

Validation checks dataset metadata without assuming perfect input. The current
checks warn on missing or unrecognized licenses, tiers, cadence values, dataset
classes, incompatible verification methods, and reference/pointer records that
claim runtime artifacts. Lineage validation checks `parent_dataset` references
and cycles. Promotion checks enforce the extra requirements needed before a
dataset can move into the commons.

## Split storage: version-controlled provenance vs out-of-tree bulk

Science separates lightweight, version-controlled provenance from bulk data that
should stay off git and out of synced folders.

The resolved project data root uses this precedence:

1. `SCIENCE_DATA_ROOT`
2. `science.yaml` `data.root`
3. global `~/.config/science/config.yaml` `data.root` plus the project id
4. `./data`

`SCIENCE_DATA_ROOT` and global `data.root` must be absolute paths after `~`
expansion. A project `science.yaml` value may be absolute or relative to the
project root:

```yaml
data:
  root: /data/proj/natural-systems
```

Payload directories keep their logical names even when the physical root moves.
Logical `data/raw`, `data/processed`, and `data/external` map to
`<resolved-root>/raw`, `<resolved-root>/processed`, and
`<resolved-root>/external`.

Never commit files under the resolved data root. Keep version-controlled
provenance outside that root, using `provenance/` or `research/packages/` for
manifests, QA reports, and small frames. Do not use `data/provenance/` when the
resolved root is the default `./data`.

