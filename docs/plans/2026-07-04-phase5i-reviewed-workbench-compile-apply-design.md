# Phase 5i Design: Reviewed Workbench Compile/Apply

Date: 2026-07-04

## 1. Context

Phase 5f retired `*.edges.yaml` from normal DAG command paths. Phase 5g added a
read-only migration planner for retired edge rows. Phase 5h added the first
write boundary in that migration path:

```bash
science dag scaffold-retired-edge-workbench \
  --project ~/d/protein-landscape \
  --dag h01-multi-manifold-protein-universe \
  --focal-hypothesis hypothesis:h01-multi-manifold-protein-universe \
  --output doc/figures/dags/h01-multi-manifold-protein-universe.workbench.yaml
```

Dogfooding that path on `~/d/protein-landscape` currently yields six ready rows,
zero blockers, zero skipped rows, zero evidence warnings, and six
`predicate_review_required` diagnostics. The scaffold is a reviewable workbench
file, not compiled proposition state.

The existing lower-level `compile_workbench(...)` function already lowers a
`WorkbenchFile` into proposition and evidence-line entities, and
`science dag workbench --check <file>` already compiles on a scratch project and
diffs the canonical workbench text. What is missing is the reviewed mutation
surface: a command that takes an edited workbench file, writes the compiled
entities in the real project, and rewrites the workbench to canonical form.

One important caveat: the current low-level workbench writer is a
deterministic-path writer, not a safe merge for authored prose. It delegates to
`write_entity_file(...)` with a fixed empty body template, and
`write_entity_file(...)` replaces the entire Markdown file body. Phase 5i must
not expose that clobbering behavior as the reviewed apply surface.

## 2. Goal

Add a narrow reviewed apply surface for workbench files:

```bash
science dag apply-workbench \
  --project <root> \
  --input <path> \
  [--format table|json]
```

The command should:

- parse the reviewed `WorkbenchFile` through the strict workbench schema;
- compile it through the same semantic lowering used by `workbench --check`;
- preflight every entity and workbench file write before mutating the project;
- write proposition and evidence-line entity frontmatter while preserving
  existing authored bodies;
- rewrite the input workbench file to the canonical normalized form;
- make a clean rerun a no-op, without timestamp churn;
- leave retired `*.edges.yaml` and DOT files untouched.

This is the compile/apply counterpart to Phase 5h's scaffold writer. Phase 5h
writes the editable projection; Phase 5i applies the reviewed projection into
canonical entity state.

## 3. Non-Goals

- Do not infer better predicates from `legacy_relation_label`.
- Do not mutate retired `*.edges.yaml` files.
- Do not delete retired DAG files after successful compile.
- Do not archive or mark retired rows as migrated.
- Do not add a relation-to-predicate registry.
- Do not change default DAG render/validate/audit to read retired YAML.
- Do not make `workbench --check` write files.
- Do not make `compile_workbench(...)` less strict about workbench schema
  validation.

Retiring or archiving the source retired-edge file after successful dogfood is a
later cleanup phase.

## 4. Approaches Considered

### A. Add `science dag apply-workbench` as a named mutation command

Chosen. A flat command keeps the write boundary explicit and avoids overloading
the existing `dag workbench --check` read-only gate. The verb "apply" matches
the Phase 4e pattern where reviewed artifacts become project mutations only
through a named apply command.

### B. Add `science dag workbench --apply <file>`

Rejected. `dag workbench --check` is currently a read-only CI gate. Adding an
apply flag to the same command makes the dangerous path differ by one option and
weakens the existing "check never writes" mental model.

### C. Tell users to call `compile_workbench(...)` manually

Rejected. The lower-level function writes immediately, replaces existing entity
bodies with a fixed empty template, and has no CLI preflight, conflict
reporting, or canonical workbench update. The migration path needs a reviewed,
reproducible command surface.

## 5. Command Surface

Add a flat DAG command:

```bash
science dag apply-workbench \
  --project <root> \
  --input <path> \
  [--format table|json]
```

`--input` is required. Relative paths resolve against the project root, not the
current shell directory. The input path must stay under the project root.

The command report should include:

- input workbench path;
- status: `applied` or `no-op`;
- row count;
- proposition entity count;
- evidence-line entity count;
- changed path count;
- project-relative changed paths;
- canonical workbench path.

The command should not add `--force` in this phase. If a file conflict exists,
the command fails before writing.

## 6. Compile And Preflight Flow

The command should not call the current real-project writer first and discover
problems afterward. It needs a preflight boundary:

1. **Read and hash input.** Read the input workbench bytes once and keep their
   SHA-256. Before rewriting the canonical workbench at the end, re-read the
   input path and require the bytes to match the parsed hash. This makes the
   "file unchanged since parse" preflight check concrete.
2. **Semantic compile in scratch.** Parse the input YAML as `WorkbenchFile`, run
   `compile_workbench(...)` against a temporary scratch project, and serialize
   `serialize_canonical(result)`. This reuses the existing workbench semantics
   and catches schema, enum, bundle-membership, evidence-stub, and ID-minting
   failures without touching the real project.
3. **Real write plan.** Convert the compile result into planned file edits for
   the real project: one edit per compiled proposition, one edit per compiled
   evidence line, plus one edit for the input workbench's canonical YAML.

The real write plan should render final entity text in memory before writing.
That planner can reuse the same typed entities returned by `compile_workbench`,
but it must not call the existing workbench private writer during preflight,
because that writer writes immediately and replaces bodies.

To avoid a second drifting frontmatter implementation, Phase 5i should extract a
pure entity renderer in `entities.py`, for example:

```python
render_entity_text(entity, *, body: str, created: str, updated: str) -> str
```

`write_entity_file(...)` and the Phase 5i write planner should both call this
renderer. The existing writer can keep its current date policy; the apply
planner supplies different `created`/`updated` values after it has compared the
existing file. The renderer should own the single canonical frontmatter
assembly: `model_dump(mode="json", exclude_none=True)`, `kind`, default
`status`, derived-field removal, and final Markdown rendering.

Preflight checks:

- every target path stays under the project root;
- every target entity path matches the entity kind and local id policy;
- an existing target file must parse as the same entity id and kind;
- malformed existing target files fail loud instead of being overwritten;
- an existing different-kind or different-id file at the target path fails;
- existing entity bodies are preserved when updating deterministic target paths
  for both propositions and evidence lines;
- duplicate planned writes to the same path must have identical final text;
- the input workbench file must still exist and match the parsed input hash
  before the canonical rewrite;
- the input workbench path must not be a retired `.edges.yaml` or DOT file.

After preflight, write entity files first, then rewrite the workbench to
canonical form. This order avoids committing canonical workbench references to
entity files that were never written. There is no cross-file rollback guarantee;
the command should preflight aggressively and report any late write failure with
the already-written paths.

## 7. Entity Write Semantics

The current `compile_workbench(...)` writer is a deterministic-path write, not a
body-preserving merge. It writes a fixed template body through
`write_entity_file(...)`. Phase 5i's CLI apply surface must be stricter and
body-safe.

For each compiled proposition and evidence-line entity:

- if the target file is new, render it with the standard workbench template
  body, `created = apply date`, and `updated = apply date`;
- if the target file exists, parse frontmatter and body, require matching id and
  kind/type, and preserve the existing body exactly;
- if the rendered frontmatter plus preserved body is byte-identical to the
  existing file, do not rewrite it;
- if only the generated `updated` date would differ, preserve the file and
  report no change;
- if entity semantic frontmatter differs, preserve `created`, set `updated` to
  the apply date, preserve the body, and write the rendered file.

This avoids timestamp churn when the user reruns the same reviewed workbench.
It also prevents the most dangerous failure mode: a later workbench apply must
not erase authored proposition summaries or evidence-line notes. The same rule
applies to evidence-line entities because evidence-line bodies are also
Markdown files and may be hand-authored after the first compile.

The lower-level `compile_workbench(...)` can keep its current behavior for
existing callers and tests, but its writer should be refactored to share the
pure renderer described above. The new apply planner gets body-preserving
semantics by choosing the body and dates explicitly before rendering.

Evidence-line IDs remain the deterministic IDs already produced by
`compile_workbench`: `<proposition-local-part>-ev<index>`. Reordering inline
evidence stubs is therefore a semantic edit, because it changes which evidence
substance occupies each deterministic evidence-line id.

## 8. Workbench Canonicalization

The input workbench is rewritten to `serialize_canonical(compile_result)`.
That means:

- id-less rows gain deterministic proposition ids;
- inline evidence stubs are replaced by evidence-line references;
- rows and evidence refs are sorted by the existing canonical serializer;
- strict workbench keys are preserved and review-only diagnostics remain absent.

After a successful apply, `science dag workbench --check <input>` should pass.
If it does not, that is a postflight failure in Phase 5i.

## 9. Error Handling

Fail before writing for:

- missing input file;
- input path outside the project root;
- invalid workbench YAML/schema;
- workbench compile errors;
- malformed existing entity target files;
- target path conflicts;
- different content at a target file that cannot be attributed to the same
  compiled entity id/kind;
- input workbench bytes changed between parse and canonical rewrite;
- duplicate planned writes with different final bytes.

Fail after writing only for filesystem errors that occur despite preflight. The
error report should include the project-relative paths already written so a user
can inspect and repair deliberately.

## 10. Protein-Landscape Acceptance Fixture

The real acceptance fixture is the current six-row `~/d/protein-landscape`
retired-edge migration target:

```text
project: ~/d/protein-landscape
dag: h01-multi-manifold-protein-universe
focal_hypothesis: hypothesis:h01-multi-manifold-protein-universe
workbench: doc/figures/dags/h01-multi-manifold-protein-universe.workbench.yaml
```

The current migration plan for that DAG has:

- `rows: 6`;
- `ready: 6`;
- `blocked: 0`;
- `skipped: 0`;
- `evidence_warnings: 0`;
- `predicate_review_required: 6`;
- ten total inline evidence stubs.

Phase 5i acceptance should use these six rows in a disposable copy or reviewed
project branch:

1. Scaffold or use the reviewed workbench file.
2. Run `science dag apply-workbench --project ~/d/protein-landscape --input
   doc/figures/dags/h01-multi-manifold-protein-universe.workbench.yaml`.
3. Assert six proposition files and ten evidence-line files are created or
   updated.
4. Assert the workbench file is canonical and `science dag workbench --check`
   exits 0.
5. Assert `science dag validate --dag h01-multi-manifold-protein-universe`
   no longer reports missing proposition edges for the six retired pairs.
6. Assert the retired `.edges.yaml` file and DOT file are unchanged.
7. Rerun `apply-workbench` and assert `status: no-op` with no entity timestamp
   churn.

The six rows still require semantic predicate review. Phase 5i should not treat
the conservative `predicate: affects` default as a proof that review happened;
it only applies the reviewed workbench presented to it.

The validate assertion is intentionally about `(subject, object)` wiring.
`validate_project(...)` loads compiled relational propositions through
`load_relational_propositions(...)` and counts matches by `(prop.subject,
prop.object)` against DOT edge occurrences. It does not require legacy retired
edge IDs for the `proposition_edge_missing` check, though those IDs are still
preserved for lineage.

## 11. Tests

Unit tests:

- apply plan renders proposition, evidence-line, and canonical workbench edits
  without writing during preflight;
- id-less rows mint deterministic proposition ids;
- inline evidence stubs become deterministic evidence-line refs;
- existing matching entity files are no-op on rerun;
- existing proposition and evidence-line Markdown bodies are preserved on
  re-apply;
- changed semantic content advances `updated` while preserving `created`;
- unchanged semantic content does not advance `updated`;
- `write_entity_file(...)` and the apply planner share one pure entity text
  renderer;
- malformed existing target files fail before writing;
- input workbench hash drift before canonical rewrite fails before writing the
  canonical workbench;
- target path conflicts fail before writing;
- duplicate planned writes with different final bytes fail.

CLI tests:

- `dag apply-workbench --input <file>` writes entities and canonicalizes the
  workbench;
- JSON output reports `applied` vs `no-op`;
- relative input paths resolve against `--project`;
- `dag workbench --check <file>` passes after apply;
- the command refuses retired `.edges.yaml` and DOT input paths;
- invalid workbench files surface as Click errors, not tracebacks.

Real-project smoke:

- run the six-row protein-landscape fixture on a disposable copy or reviewed
  project branch;
- confirm the exact row/entity/evidence counts above;
- confirm rerun is a no-op.

## 12. Acceptance Criteria

- Phase 5h remains a workbench-only scaffold writer.
- `workbench --check` remains read-only.
- `apply-workbench` is the only new Phase 5i mutation surface.
- Successful apply writes compiled entities and canonical workbench text.
- Clean reruns are no-op and do not churn dates.
- The six protein-landscape retired rows can be compiled into proposition-backed
  DAG edges after review.
