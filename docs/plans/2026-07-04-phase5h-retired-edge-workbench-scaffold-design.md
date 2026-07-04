# Phase 5h Design: Retired Edge Workbench Scaffold

Date: 2026-07-04

## 1. Context

Phase 5f retired `*.edges.yaml` from normal DAG command paths. Phase 5g added
the explicit, read-only `science dag retired-edge-migration-plan` surface, which
can turn retired edge rows into JSON/table diagnostics or strict workbench YAML
printed to stdout.

Dogfooding Phase 5g on `~/d/protein-landscape` found one real remaining retired
file:

```text
doc/figures/dags/h01-multi-manifold-protein-universe.edges.yaml
```

With the reviewed bundle frame
`hypothesis:h01-multi-manifold-protein-universe`, the planner produces six
workbench-compatible rows:

| edge | legacy relation | generated triple | identification | support |
| --- | --- | --- | --- | --- |
| 1 | `biases` | `snapshots affects pc1` | `observational` | 2 tasks + 1 paper |
| 2 | `yields` | `lenses affects orthogonality` | `observational` | 2 tasks + 1 paper |
| 3 | `motivates` | `pc1 affects residualization` | `structural` | 1 task |
| 4 | `improves` | `residualization affects coherence` | `interventional` | 1 task |
| 5 | `reframes` | `orthogonality affects interaction` | `none` | 1 task |
| 6 | `estimates` | `interaction affects robust` | `none` | 1 paper |

The rows preserve retired identity (`legacy_patch`, `legacy_edge_id`,
`legacy_relation_label`) and evidence refs cleanly. The unresolved semantic
issue is predicate review: every generated row uses the conservative
`predicate: affects` default because legacy `relation` is free text.

That means the next step should create a durable review artifact, not compile
propositions. Authors need a file they can edit, run through the existing
workbench parser/check workflow, and review before entity writes.

## 2. Goal

Add a narrow scaffold command that writes a reviewable workbench draft from the
Phase 5g migration plan.

The command should:

- rebuild the retired-edge migration plan from live project state;
- require selected rows to be workbench-compatible;
- write a strict `WorkbenchFile` YAML document to a requested output path;
- preserve all migrated lineage and evidence stubs emitted by Phase 5g;
- be idempotent when rerun against an identical scaffold;
- stop before `compile_workbench`.

This is the first write boundary after Phase 5g, but it writes only the editable
workbench projection. It does not write propositions, evidence-line entities,
DOT files, or retired YAML.

## 3. Non-Goals

- Do not compile workbench rows into proposition/evidence-line entities.
- Do not add an entity apply surface.
- Do not edit, delete, or archive retired `*.edges.yaml`.
- Do not edit DOT files.
- Do not infer precise predicates from legacy relation labels.
- Do not add a relation-to-predicate mapping registry in Phase 5h.
- Do not store review-only fields in workbench YAML; `WorkbenchRow` forbids
  unknown keys.

## 4. Command Surface

Add a flat DAG command:

```bash
science dag scaffold-retired-edge-workbench \
  --project <root> \
  --dag <slug> \
  --focal-hypothesis <hypothesis-ref> \
  --output <path> \
  [--format table|json]
```

For the dogfood target:

```bash
science dag scaffold-retired-edge-workbench \
  --project ~/d/protein-landscape \
  --dag h01-multi-manifold-protein-universe \
  --focal-hypothesis hypothesis:h01-multi-manifold-protein-universe \
  --output doc/figures/dags/h01-multi-manifold-protein-universe.workbench.yaml
```

The command is intentionally separate from
`retired-edge-migration-plan --format workbench`. Phase 5g remains pure stdout
planning; Phase 5h is the explicit file-write boundary.

`--format` controls the command's report, not the written workbench file:

- `table`: concise action summary;
- `json`: machine-readable summary with output path, selected rows, and no-op /
  written status.

## 5. Selection Rules

Phase 5h starts with one DAG at a time. `--dag` is required so the scaffold
writer has a single obvious output artifact and cannot accidentally combine
unrelated patch rows.

The command should call `build_retired_edge_migration_plan(project, dag=...,
focal_hypothesis=...)` and select rows whose status is `ready` and whose
`proposed_row` is present.

Fail before writing if:

- the retired edge file does not exist;
- the plan has zero rows;
- any row in the selected DAG is `blocked`;
- any row in the selected DAG is `skipped`, including
  `matching-proposition-exists` and `no-claim-support-content`;
- evidence warnings are present, unless a later design adds an explicit
  `--allow-evidence-warnings`;
- `--focal-hypothesis` is missing.

This strictness is deliberate. A scaffold is a durable reviewed artifact; it
should not silently omit rows from the retired file or hide migration debt.
Phase 5g guarantees ready rows carry `proposed_row`; Phase 5h treats a ready row
without one as an internal planner invariant violation rather than a recoverable
selection case.

## 6. Output Path Semantics

`--output` is required. Relative paths are resolved against the project root,
not the current shell directory. JSON/table reports should display project-
relative paths when possible, using repo-local paths rather than expanded
machine paths in human-facing text.

The output path may be anywhere under the target project, but the recommended
path is alongside the retired DAG file:

```text
doc/figures/dags/<dag>.workbench.yaml
```

Fail before writing if:

- the output path escapes the project root;
- the parent directory does not exist;
- the output path is the retired `.edges.yaml` file;
- the output path is a DOT file;
- the output path already exists with different bytes.

If the output path already exists with identical bytes, report `no-op` and exit
0. This makes reruns safe after a successful scaffold.

Phase 5h should not add `--force` or `--update`. Updating a reviewed workbench
after manual edits needs a separate merge/update design.

## 7. Written Workbench Shape

The written file is exactly the strict `WorkbenchFile` YAML already produced by
Phase 5g's `migration_plan_to_workbench_yaml(plan)`:

- top-level `focal_hypothesis`;
- `rows`;
- only fields accepted by `WorkbenchRow`;
- no review diagnostics such as `predicate_review_required`, `blockers`, or
  `notes`.

The scaffold preserves:

- `subject`, `predicate`, `object`;
- `patch`;
- `polarity`;
- `claim_layer`;
- `identification_strength`;
- `legacy_relation_label`;
- `legacy_patch`;
- `legacy_edge_id`;
- `discusses`;
- inline evidence stubs.

The command should parse the rendered YAML back through `WorkbenchFile` before
writing. This keeps the writer honest and avoids persisting a file that the
existing workbench parser rejects.

## 8. Review Workflow

Phase 5h creates the durable file authors review:

1. Run `scaffold-retired-edge-workbench`.
2. Review and edit the workbench, especially `predicate`, `claim_layer`,
   `identification_strength`, `polarity`, and evidence stubs.
3. Run `science dag workbench --check <file>` as a parse/compile/canonical
   diff gate. A scaffold that still contains inline evidence stubs may fail the
   canonical byte-for-byte check until the normalized refs are reviewed and
   committed; that failure is review feedback, not a scaffold-writer failure.
4. Only after semantic and canonical review, a later command or manual workflow
   may call `compile_workbench`.

For the six `protein-landscape` rows, predicate review is expected. The scaffold
will still contain `predicate: affects`; the preserved `legacy_relation_label`
is the review cue.

## 9. Error Handling

Fail loud for command misuse and stale project state. The command should surface
the same row blockers as Phase 5g, but it should not write a partial file when
any selected row is blocked or skipped.

Suggested exit behavior:

| condition | behavior |
| --- | --- |
| all rows ready, output absent | write file, exit 0 |
| output exists with identical bytes | no-op report, exit 0 |
| output exists with different bytes | fail, exit non-zero |
| row blocker/skipped row/evidence warning | fail, exit non-zero |
| invalid output path | fail, exit non-zero |

No rollback machinery is needed because the command writes at most one file and
performs all validation before writing.

## 10. Testing

Unit tests:

- builds a scaffold from a ready Phase 5g fixture;
- written YAML validates as `WorkbenchFile`;
- output preserves `legacy_patch`, `legacy_edge_id`, `legacy_relation_label`,
  `focal_hypothesis`, and evidence stubs;
- missing `--focal-hypothesis` fails before writing;
- missing retired edge files and empty migration plans fail before writing;
- blocked rows fail before writing;
- skipped rows fail before writing for both `matching-proposition-exists` and
  `no-claim-support-content`;
- output path escaping the project root fails;
- identical existing file is a no-op;
- different existing file fails.

CLI tests:

- command writes the expected file and table report;
- `--format json` reports `written` vs `no-op`;
- relative `--output` resolves against `--project`;
- missing retired edge files are surfaced as Click errors, not tracebacks;
- the command does not compile propositions or evidence lines.

Real-project smoke:

- on `~/d/protein-landscape`, the command can scaffold
  `doc/figures/dags/h01-multi-manifold-protein-universe.workbench.yaml` from
  the six current retired rows in a disposable copy or dedicated test fixture;
- `science dag workbench --check` can parse and compile the resulting file on a
  scratch project; a canonical diff is acceptable because inline evidence stubs
  normally normalize to evidence-line refs before the file reaches fixpoint.

## 11. Acceptance Criteria

- Phase 5g remains read-only.
- Phase 5h writes only one explicit workbench file.
- No proposition/evidence-line/DOT/retired-YAML files are written.
- The writer refuses partial migrations.
- Existing reviewed workbenches are not overwritten.
- The written file is strict `WorkbenchFile` YAML.
- The six `protein-landscape` rows can be scaffolded with the reviewed focal
  hypothesis while preserving legacy identity and support refs.

## 12. Follow-Up Work

- Design a reviewed update/merge mode for existing scaffold files.
- Design compile/apply guidance after manual predicate review.
- Add project-specific relation-to-predicate review aids if repeated legacy
  labels justify it.
- Once migrated propositions are compiled and validated, design retired YAML
  archive/removal for the corresponding edge file.
