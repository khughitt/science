# Phase 5j Design: Derived Retired Edge Closure

Date: 2026-07-04

## 1. Context

Phase 5f removed retired `*.edges.yaml` from normal DAG render/validate/audit
paths. Phase 5g added a read-only migration planner. Phase 5h wrote reviewed
workbench scaffolds. Phase 5i applied reviewed workbenches into proposition and
evidence-line entities.

The first real apply in `~/d/protein-landscape` migrated the six retired rows in
`doc/figures/dags/h01-multi-manifold-protein-universe.edges.yaml` into six
draft propositions and ten evidence-line stubs. The generated propositions carry
the important lineage fields:

- `legacy_patch: h01-multi-manifold-protein-universe`
- `legacy_edge_id: <retired row id>`
- relational identity through `subject` and `object`

The remaining problem is closure. After a successful apply, the current planner
already detects the generated propositions by `subject` / `object`, but it
classifies those retired rows as generic `skipped` rows with the
`matching-proposition-exists` blocker. That keeps them out of workbench-ready
output, but it also makes `scaffold-retired-edge-workbench` fail before write
because Phase 5h treats every skipped row as migration debt. Phase 5j promotes
the lineage-backed subset of those pair matches from generic `skipped` to a
diagnosed `closed` state.

The closure fact already exists in the generated proposition entities, so Phase
5j should derive closure from live proposition state before adding any separate
closure file or decision log.

## 2. Goal

Make retired-edge migration closure a deterministic view over compiled
relational propositions.

A retired edge row is closed when the project has exactly one live relational
proposition whose:

- `legacy_patch` equals the DAG slug;
- `legacy_edge_id` equals the retired row id;
- `subject` equals the retired row source;
- `object` equals the retired row target.

Closed rows should remain visible in migration diagnostics, but they should no
longer be treated as skipped migration debt by the scaffold writer. The six
protein-landscape rows migrated by Phase 5i are the acceptance fixture for this
transition: today they are `skipped`; after Phase 5j they should be `closed`.

## 3. Non-Goals

- Do not write an explicit closure record in Phase 5j.
- Do not mutate, delete, archive, or rewrite retired `*.edges.yaml` files.
- Do not mutate generated proposition or evidence-line entities.
- Do not infer better predicates from `legacy_relation_label`.
- Do not polish generated proposition/evidence-line bodies.
- Do not solve the project-wide aggregate-retirement backlog in
  `~/d/protein-landscape`.
- Do not change normal DAG render/validate/audit to read retired YAML.

Explicit closure records can be revisited later if we need reviewer notes,
non-proposition closure, or audit metadata beyond what generated propositions
carry.

## 4. Approaches Considered

### A. Derived closure from proposition lineage

Chosen. The generated propositions are the canonical migrated state. They already
carry `legacy_patch`, `legacy_edge_id`, `subject`, and `object`, and they are
what the DAG view uses going forward. Treating them as the closure source keeps
the migration path simple and avoids a second record that can drift.

### B. Append an explicit migrated-edge closure log

Rejected for Phase 5j. A log could carry reviewer notes and historical audit
context, but it would need freshness, conflict, and deduplication semantics. That
extra state is not needed to suppress already-applied rows after Phase 5i.

### C. Edit retired `*.edges.yaml` rows in place

Rejected. Retired YAML is a migration input only. Updating it would revive it as
a state-bearing surface and weaken the Phase 5f boundary.

## 5. Closure Index

Add a planner-internal closure index built from live relational propositions.
The index should reuse the same proposition loading path as
`load_relational_propositions(project_root)`, then inspect proposition lineage
fields.

The primary key is:

```text
(legacy_patch, legacy_edge_id)
```

Only propositions with both fields present participate in this index.
Propositions without `legacy_patch` / `legacy_edge_id` may still participate in
the older pair-only matching diagnostic, but they do not close a retired row.

The index value should include enough detail for diagnostics:

- proposition id;
- `subject`;
- `object`;
- `legacy_patch`;
- `legacy_edge_id`;
- source path from `PropositionEntity.file_path`.

The implementation should avoid introducing a closure file format. The closure
index is recomputed from live project state on every planner run.

This depends on the same entity-load path already used by the Phase 5g planner:
`load_relational_propositions(project_root)` delegates to
`load_local_entity_index(project_root)`. Dogfooding against
`~/d/protein-landscape` confirms that this path loads relational propositions
despite that project's unrelated aggregate-retirement validation backlog.

## 6. Row Classification

Extend the migration row status vocabulary with `closed`:

```python
MigrationStatus = Literal["ready", "blocked", "skipped", "closed"]
```

Classification order matters:

1. Hard identity failures short-circuit to `blocked`: missing `id`, missing
   `source`, missing `target`, invalid edge shape, or invalid identification.
   A row whose identity cannot be trusted cannot be closed.
2. For trusted row identity, check derived closure by `(dag, edge.id)`.
3. If exactly one lineage-backed proposition exists and `subject` / `object`
   match, classify the row as `closed`, even if the retired file now has soft
   state blockers such as `dot-missing` or `eliminated-edge`. The migrated
   proposition is the live state; the retired row is no longer the authority.
4. If lineage-backed propositions exist but the match is ambiguous or
   inconsistent, classify the row as `blocked`.
5. Fall back to current no-content and pair-only matching behavior.
6. Otherwise classify as `ready` or `blocked` using the existing Phase 5g rules.

This ordering ensures closure never hides malformed retired-row identity, while
still allowing migrated live proposition state to close retired rows whose old
DOT or retired-edge state has drifted.

Closed rows should carry a clear note such as `derived-closure` and a
`closed_by` payload containing the migrated proposition id.

## 7. Integrity Cases

Derived closure is intentionally strict:

- **Exactly one matching lineage proposition:** row is `closed`.
- **No matching lineage proposition:** proceed with existing planning rules.
- **Multiple propositions with the same `(legacy_patch, legacy_edge_id)`:** row
  is `blocked` with `duplicate-legacy-edge-claim`.
- **Lineage key matches but subject/object differ:** row is `blocked` with
  `legacy-edge-claim-mismatch`; include the proposition id and observed
  subject/object in diagnostics.
- **Pair-only proposition exists but lacks lineage:** retain the existing
  `matching-proposition-exists` skipped behavior and note that the matching
  proposition lacks `legacy_patch` / `legacy_edge_id`.
- **Closed proposition later deleted:** closure disappears on the next planner
  run, so the retired row resurfaces as ready/blocked according to current live
  state.

The mismatch and duplicate cases are blockers rather than skipped rows because
they indicate inconsistent migrated state, not completed work.

## 8. Report Contract

The planner JSON summary should add a `closed` count while preserving the
existing `ready`, `blocked`, and `skipped` counts.

Each row should expose:

- `status: "closed"` for derived closure;
- `closed_by`: list of proposition ids, normally length 1;
- `closure_reason`: `derived-legacy-edge-lineage`;
- `matching_propositions` only for pair-only diagnostics that are not derived
  closure.

For blocked closure conflicts, rows should expose the blocker and the conflicting
proposition ids. Do not hide closure conflicts under `skipped`.

Table output should make closure obvious, for example:

```text
h01-multi-manifold-protein-universe#1: snapshots -> pc1 closed by proposition:snapshots-affects-pc1
```

The exact table wording is less important than the stable JSON fields.

## 9. Scaffold Behavior

`scaffold-retired-edge-workbench` should treat closed rows as completed, not as
an error.

Rules:

- Closed rows are excluded from the written workbench.
- Blocked rows remain fail-before-write.
- Skipped rows from non-closure causes remain fail-before-write for now, matching
  Phase 5h strictness.
- Evidence warnings remain fail-before-write.
- If all rows are closed, report `complete`, do not render a workbench YAML
  document, and do not inspect or rewrite the output path.
- If some rows are closed and the remaining rows are ready, write a workbench
  containing only the remaining ready rows.

This is the key behavior change from Phase 5h. Phase 5h deliberately refused to
silently omit skipped rows. Phase 5j makes derived closure a first-class,
diagnosed completion state, so excluding closed rows is not silent omission.

The command report should include:

- total rows;
- closed rows;
- written rows;
- status: `written`, `no-op`, or `complete`;
- closed proposition ids in JSON output.

The all-closed branch must short-circuit before calling
`migration_plan_to_workbench_yaml(plan)`. That helper deliberately raises when
there are no compile-compatible rows. The complete branch is not a rendering
case; it is the "nothing remains to scaffold" case.

Status definitions:

- `written`: at least one ready row was rendered to a new workbench file;
- `no-op`: at least one ready row was rendered, and the output path already
  existed with identical bytes;
- `complete`: no rows remain to scaffold because every retired row is closed by
  derived proposition lineage.

## 10. CLI Surface

No new command is required.

Update existing surfaces:

```bash
science dag retired-edge-migration-plan --project <root> --dag <slug> --format json
science dag retired-edge-migration-plan --project <root> --dag <slug> --format table
science dag scaffold-retired-edge-workbench --project <root> --dag <slug> ...
```

The workbench scaffold command's `complete` status is new. Table output should
say that no workbench was written because every row is already closed by
proposition lineage.

## 11. Protein-Landscape Acceptance Fixture

With the Phase 5i commit applied in `~/d/protein-landscape`, running the planner
against `h01-multi-manifold-protein-universe` should report:

- `rows: 6`;
- `closed: 6`;
- `ready: 0`;
- `blocked: 0`;
- `skipped: 0`;
- each row closed by the matching generated proposition id.

Running the scaffold command for the same DAG should not rewrite the existing
workbench or create a new one. It should report complete closure. If an existing
workbench file is supplied as `--output`, the command should still avoid writes
when there are no rows to scaffold.

The broader `science validate --verbose` failures in `~/d/protein-landscape`
remain unrelated aggregate-retirement backlog and should not be part of Phase 5j
acceptance.

## 12. Tests

Focused unit tests should cover:

- derived closure from one proposition with matching `legacy_patch`,
  `legacy_edge_id`, `subject`, and `object`;
- duplicate lineage claims block the retired row;
- lineage id match with subject/object mismatch blocks the retired row;
- pair-only matching without lineage remains the existing skipped diagnostic;
- deleted/missing proposition causes the row to resurface as ready when the
  retired row is otherwise migration-ready;
- JSON summary includes `closed`;
- table output includes the closing proposition id;
- scaffold excludes closed rows but writes remaining ready rows;
- scaffold returns `complete` and writes nothing when all rows are closed.

Real-project smoke should run the planner against the six protein-landscape rows
after Phase 5i apply and inspect the closure counts. This is an observation gate,
not a dependency on the broader project validation being clean.

## 13. Future Work

After derived closure is in place, later phases can decide whether to:

- archive or remove retired `*.edges.yaml` files once all rows are closed;
- add explicit closure records for reviewer notes or non-proposition closures;
- add a relation-to-predicate review/mapping surface for legacy labels;
- scaffold prose improvements for generated proposition and evidence-line
  bodies.

Those phases should build on derived closure rather than reintroducing retired
YAML as an authoritative source.
