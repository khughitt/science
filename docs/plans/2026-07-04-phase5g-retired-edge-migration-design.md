# Phase 5g Design: Retired DAG Edge Migration Planning

Date: 2026-07-04

## 1. Context

Phase 5f retired `*.edges.yaml` from normal DAG command paths. Render,
validate, audit, number, init, and inventory now treat compiled relational
propositions as the semantic edge source and DOT files as the view topology.
The only normal CLI path that still reads retired YAML is the explicit
inspection surface:

```bash
science dag retired-edges --project <root> [--dag <slug>] [--format table|json]
```

That command sizes migration debt but does not help authors move remaining
curation into the proposition/workbench model. In sampled active projects, most
projects now report no retired edge files. `protein-landscape` still has one
retired file with six migration-worthy rows, each carrying claim text and support
refs. That is the target shape for Phase 5g: small, reviewable migration
candidates rather than a large automatic conversion.

## 2. Goal

Add a deterministic, read-only migration planner for retired DAG edge rows. The
planner should translate migration-worthy `*.edges.yaml` rows into explicit
candidate workbench rows and blockers, without compiling propositions, writing
entities, or making retired YAML authoritative again.

The output is a review artifact. It should make remaining migration work easier
to inspect and edit, while preserving the Phase 5f boundary:

- retired YAML is a migration input only;
- workbenches remain the editable projection for proposition-backed DAG edges;
- `compile_workbench` remains the only writer from workbench rows into
  proposition/evidence-line entities;
- default DAG commands continue to ignore retired YAML.

## 3. Non-Goals

- Do not add an apply command in Phase 5g.
- Do not compile proposed rows into proposition entities.
- Do not delete or modify retired `*.edges.yaml` files.
- Do not make `edge_status` authored in the new model.
- Do not infer belief or grounding from retired YAML.
- Do not auto-convert arbitrary free-text legacy relations into precise
  predicate semantics without review.
- Do not redesign proposition-backed DAG staleness; that remains separate work.

## 4. Approaches Considered

### A. Read-only migration plan plus workbench draft output

The planner reads the existing retired-edge report, classifies rows, and emits a
JSON/table report. It can also emit a draft workbench YAML shape for rows that
are structurally safe enough to stage. The draft is not written or compiled by
default.

Chosen. It moves migration forward while keeping semantic review between retired
YAML and executable proposition state.

### B. Direct workbench writer

The command writes a new `<patch>.workbench.yaml` file directly.

Rejected for Phase 5g. It is useful later, but the first migration surface should
show exactly what would be produced and where the semantic assumptions are. A
writer can be added after the plan format is dogfooded.

### C. Full migration/apply

The command reads retired YAML, writes workbench rows, and compiles propositions
and evidence lines.

Rejected. This gives a retired compatibility source too much authority and
collapses review, authoring, and compilation into one step.

## 5. Command Surface

Add a planning surface under the explicit retired-edge namespace. The exact CLI
can be either a subcommand or a flag, but it should read as a planner, not as
normal DAG validation:

```bash
science dag retired-edges plan-migration \
  --project <root> \
  [--dag <slug>] \
  [--format table|json|workbench]
```

If Click nesting makes this awkward, a flat sibling is acceptable:

```bash
science dag retired-edge-migration-plan \
  --project <root> \
  [--dag <slug>] \
  [--format table|json|workbench]
```

The planner is read-only for every format. `--format workbench` prints a draft
workbench document to stdout; it does not write a file. A later phase may add an
explicit `--output` or writer command after review.

## 6. Planner Input

The planner consumes the same explicit retired-edge discovery path as
`build_retired_edges_report`. It must not be imported by default render,
validate, audit, number, init, or inventory paths.

For each retired row, the planner needs more than the current summary row exposes.
It should preserve raw fields required for candidate construction:

- `dag`;
- retired YAML path;
- `id`;
- `source`;
- `target`;
- `relation`;
- `original_label`;
- `description`;
- `edge_status`;
- `identification`;
- `data_support`;
- `lit_support`;
- `eliminated_by`;
- `source_label`;
- `target_label`;
- `caveats`.

The existing `RetiredEdgeRow` can be extended, or the planner can have its own
internal row type that is built from the same YAML parse. The important boundary
is shared discovery and parsing behavior, not shared summary shape.

## 7. Row Classification

Each retired edge row should be classified as one of:

- `ready`: a draft workbench row can be produced without losing required
  identity fields;
- `blocked`: the row has migration-worthy content, but a required field is
  missing or structurally ambiguous;
- `skipped`: the row is already covered by a compiled proposition or has no
  claim/support content worth migrating.

Initial blocker reasons:

- `missing-source`;
- `missing-target`;
- `missing-edge-id`;
- `dot-missing`;
- `invalid-identification`;
- `eliminated-edge`;
- `predicate-review-required` if the implementation chooses to block instead of
  scaffold conservative predicates;
- `matching-proposition-exists`.

`matching-proposition-exists` should normally be `skipped`, not an error. If a
matching proposition exists but lacks `legacy_patch` / `legacy_edge_id`, the
planner may report a non-blocking note so authors can decide whether to add
lineage metadata later.

## 8. Workbench Row Mapping

For rows classified as `ready`, produce a candidate `WorkbenchRow`-compatible
mapping:

```yaml
subject: <retired source>
predicate: affects
object: <retired target>
patch: <dag slug>
legacy_relation_label: <relation or original_label>
legacy_patch: <dag slug>
legacy_edge_id: <retired id>
claim_layer: <derived claim layer>
identification_strength: <mapped identification>
polarity: <derived polarity>
evidence:
  - ...
```

### Predicate

Legacy DAG `relation` is free text (`biases`, `yields`, `motivates`,
`reframes`, and similar). Workbench predicates are a closed enum. The planner
must not pretend that free text is already a valid predicate.

Recommended Phase 5g behavior:

- use `predicate: affects` as the conservative directional default for
  non-eliminated DAG rows;
- copy legacy `relation` or `original_label` into `legacy_relation_label`;
- include `predicate_review_required: true` in JSON/table diagnostics for every
  row where the predicate is defaulted;
- omit `predicate_review_required` from the emitted workbench YAML itself,
  because `WorkbenchRow` forbids unknown fields.

This gives authors a usable scaffold while making the semantic review obligation
visible.

### Polarity

Map non-eliminated directional rows to `polarity: positive` by default. If a
legacy row clearly represents an absence, inhibition, or negative direction only
through free text, the planner should still avoid NLP inference and mark the row
for review rather than changing polarity automatically.

`edge_status: eliminated` rows should not become ordinary positive workbench
rows in Phase 5g. They should be blocked or skipped with `eliminated-edge`, since
their epistemic meaning belongs in dispute/refutation evidence, not in a simple
positive proposition scaffold.

### Claim Layer

Map `edge_status: structural` or `identification: structural` to
`claim_layer: structural_claim`. Otherwise default to
`claim_layer: causal_effect` for directional rows. Preserve the retired
description as evidence/source context rather than trying to infer
`mechanistic_narrative` automatically.

### Identification Strength

Map legacy identification tokens to the current enum:

- `interventional` -> `interventional`;
- `longitudinal` -> `longitudinal`;
- `observational` -> `observational`;
- `structural` -> `structural`;
- `none` -> `none`;
- missing -> `none` plus a review note.

Invalid values block the row with `invalid-identification`.

### Bundle Membership

Migrated workbench rows with `legacy_edge_id` must declare bundle membership.
The planner should make this explicit.

Default Phase 5g behavior:

- set file-level `focal_hypothesis` only when the command is scoped to one DAG
  and the user provides or configures an intended hypothesis frame;
- otherwise emit row-level `discusses` blockers or a JSON field
  `membership_required: true`;
- do not invent hypothesis ids from the DAG slug unless an existing project
  convention is discovered and validated.

This avoids producing a workbench draft that `compile_workbench` would later
reject for migrated rows with no membership.

## 9. Evidence Mapping

Retired edge rows can carry `description`, `data_support`, `lit_support`, and
`eliminated_by`. Phase 5g should not convert these into belief-bearing evidence
as if they had been authored in the new model.

For draft workbench output:

- represent `description` and support descriptions as inline `EvidenceStub`
  candidates only when they can be mapped without inventing source identity;
- use `evidence_type: literature` for `lit_support` entries with concrete
  `paper` refs;
- use `evidence_type: empirical_data` for `data_support` entries with concrete
  `task`, `dataset`, or accession-like refs;
- mark empirical stubs without `dataset_usage` as staged in the normal workbench
  compile path (`belief_eligible=False` already handles this);
- preserve raw support refs and descriptions in JSON diagnostics even when no
  workbench evidence stub is emitted.

If a support entry is structurally invalid under the retired schema, the planner
should fail loud during parse, matching the existing retired-edge inspection
surface. If it is structurally valid but not mappable to a useful workbench
source string, the row can still be `ready` with an evidence warning, because the
core proposition row may be migrated separately from evidence cleanup.

## 10. Output

### JSON

JSON output should include:

- project root;
- summary counts by status (`ready`, `blocked`, `skipped`);
- counts of `predicate_review_required`, `membership_required`, and evidence
  warnings;
- one item per retired row with source path, dag, edge id, source/target,
  classification, blockers, review notes, and a proposed row when available.

### Table

Table output should be compact:

```text
dag edge source -> target status blockers notes
```

The table should be optimized for triage, not for copying into a workbench.

### Workbench

Workbench output should print a strict `WorkbenchFile`-compatible YAML document
containing only rows that are structurally ready and compile-compatible. Because
`WorkbenchRow` forbids unknown keys, review metadata such as
`predicate_review_required` belongs in JSON/table output, not in the workbench
YAML.

If no rows are compile-compatible, workbench output should fail with an
actionable message rather than printing an empty file that looks useful.

## 11. Error Handling

Fail loud for:

- missing `science.yaml`;
- unreadable configured DAG directory;
- invalid retired YAML that the legacy schema rejects;
- `--dag` naming a retired file that does not exist;
- workbench format requested when all candidate rows are blocked/skipped.

Do not fail the entire report just because one row is blocked. Row-level blockers
are the point of the planner.

## 12. Testing

Unit tests:

- ready row maps `source`/`target` to `subject`/`object`;
- legacy relation is preserved as `legacy_relation_label`;
- legacy edge identity becomes `legacy_patch` / `legacy_edge_id`;
- default predicate marks `predicate_review_required` in JSON diagnostics;
- structural identification maps to `claim_layer: structural_claim`;
- eliminated rows do not become positive ready rows;
- matching compiled proposition causes skip;
- invalid or missing required row fields produce row blockers.

CLI tests:

- JSON output reports ready/blocked/skipped counts;
- table output includes concise blockers;
- workbench output is parseable as `WorkbenchFile`;
- workbench output omits review-only keys forbidden by the workbench schema;
- workbench output fails when all rows require membership or predicate blocking,
  if the selected implementation blocks those conditions.

Real-project smoke:

- `protein-landscape` should produce six migration candidates or six explicit
  blockers, depending on the membership/predicate policy selected in the
  implementation plan;
- projects with no retired YAML should report zero candidates cleanly.

## 13. Acceptance Criteria

- Default DAG commands still do not read retired YAML.
- The planner is the only new code path that reads retired YAML.
- Every proposed row preserves retired edge identity via `legacy_patch` and
  `legacy_edge_id`.
- Free-text legacy relations are not treated as authoritative predicates without
  visible review metadata.
- Workbench-format output validates against the strict `WorkbenchFile` model.
- No command writes a workbench, proposition, evidence-line, DOT, or retired YAML
  file in Phase 5g.

## 14. Follow-Up Work

- Add an explicit writer once the plan format is dogfooded.
- Add a reviewed relation-to-predicate mapping file if repeated legacy relation
  labels need stable project-specific mappings.
- Add proposition-backed staleness over proposition source refs, evidence lines,
  and reviewed decision records.
- Delete the retired YAML parser once inspection and migration planning report no
  production content.
