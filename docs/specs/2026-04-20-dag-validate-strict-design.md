# `science-tool dag validate [--strict]` — Design

**Date:** 2026-04-20
**Status:** proposed
**Profile scope:** research (software-profile projects opt in via the `dag:`
block, same as Phase 1)

**Depends on:**
- `2026-04-19-dag-rendering-and-audit-pipeline-design.md` (landed — Phase 1+3
  shipped the Pydantic models, ref-resolution helpers, and `dag` subcommand
  group this spec builds on).
- `2026-04-17-edge-status-dashboard-design.md` (amended 2026-04-19 to add
  `eliminated`).

**Amends:** none directly. Extends the `dag` subcommand group with a new
`validate` command and a new `schema` command; extends `dag audit` with an
implicit validation step.

**Supersedes:** the "JSON-schema validation (`dag validate --strict`)"
line-item listed as out-of-scope in the Phase 1 spec's §"Out of Scope
(Phase 2 follow-ups)".

## Goal

Introduce `science-tool dag validate` as the comprehensive health check for
a project's DAG layer, and `science-tool dag schema` as the emission
surface for the generated JSON Schema artifact. Together they close the
loop that Phase 1 deferred: Phase 1 validated *shape* at load time (via
Pydantic, inside `render`/`number`) and *ref resolution* per-entry, but
left cross-file, topology, and numeric-sanity checks un-enforced. Phase 2a
adds those checks under a standalone command and plumbs them into `dag
audit` so CI and the `/science:dag-audit` skill both see validation
findings.

`--strict` is **curation strictness**, not schema strictness — schema
strictness is always on. `--strict` adds gates that are appropriate only
once a project has finished migrating to the Phase 1 YAML layer.

## Non-Goals

- Replace the Pydantic models as runtime validator. Pydantic remains the
  SoT; the JSON Schema is a derived artifact.
- Graph-layer validation. Checking `sci:edgeStatus` / `sci:identification`
  / `sci:eliminatedBy` predicates in `knowledge/graph.trig` is Phase 2b
  (`sync-dag`), not this spec.
- Auto-fix. `dag validate` reports; mutation lives under `dag audit
  --fix` if/when desired.
- Editor integration. Publishing the JSON Schema via a stable `$id` URL
  so VS Code's YAML extension picks it up is a follow-up; v1 ships the
  schema file as package data only.

## Problem

Phase 1 enforces YAML *shape* (Pydantic models) and per-entry *ref
resolution* (task/interpretation/discussion/proposition/paper must exist
on disk) every time `render` / `number` loads a file. What it does NOT
enforce:

1. **Topology consistency between `.dot` and `.edges.yaml`.** The two files
   are independent. If a user hand-edits `.dot` to add an edge and
   forgets to re-run `dag number`, the YAML is silently missing a
   record. If they delete a YAML record without updating `.dot`, the
   renderer will style zero edges for that row.
2. **Acyclicity.** Nothing today verifies the `.dot` actually describes
   a DAG. A cycle goes unnoticed until it confuses a downstream tool.
3. **Posterior numeric sanity.** `beta: "inf"` or `hdi_low > hdi_high`
   or `prob_sign: 1.7` all deserialize to valid Python floats but are
   meaningless. The renderer's `min(4.5, 1.6 + 4·|β|)` would still
   produce a finite penwidth; the HDI-crosses-zero rule would still
   evaluate; but the edge is broken.
4. **Schema artifact drift.** A future consumer of the edges YAML (an
   editor plugin, a CI lint, a second project) will want a JSON Schema
   file. Without `dag schema`, those consumers are blocked on reading
   Pydantic models — an in-Python-only contract.
5. **Migration completeness.** The Phase 1 `identification` field
   defaults to `none` with a `DeprecationWarning`. There is no mechanism
   to say "this project has finished backfilling; a missing
   `identification` is now a hard error." This is the original motivation
   for `--strict` in the Phase 1 out-of-scope list.

Each of the above was listed in Phase 1 as deferred. This spec gathers
them into one coherent command and one derived artifact.

## Scope

### Two new commands

```
science-tool dag validate [--strict] [--dag <slug>] [--json]
science-tool dag schema   [--output PATH]
```

Plus one modification:

```
science-tool dag audit [--json]   # now implicitly runs validate too
science-tool dag audit --fix      # unchanged mutation semantics
```

### Schema source-of-truth (Q1: Pydantic-generated)

The existing Pydantic v2 models in `science_tool/dag/schema.py` remain
the runtime SoT. `EdgesYamlFile.model_json_schema()` emits a JSON Schema
draft-2020-12 document. That document is committed to the repository at:

```
science-tool/src/science_tool/dag/edges.schema.json
```

and shipped as package data (via `importlib.resources`). Downstream
consumers — editors, CI in non-Python projects, mm30 — read the schema
file; the Python runtime reads Pydantic.

A dedicated test (`test_schema_artifact.py`) asserts the committed file
equals `json.dumps(EdgesYamlFile.model_json_schema(), …)` under a canonical
serialization (sorted keys, indent=2). If a Pydantic model change alters
the generated schema and the artifact is not regenerated, the test fails
with an error message pointing at `science-tool dag schema --output
src/science_tool/dag/edges.schema.json`.

The `dag schema` command exists so that (a) the test fixup is one
command, and (b) downstream consumers who do not vendor the file can
regenerate on demand.

**Dialect:** JSON Schema draft-2020-12 (Pydantic v2 default; no override).

**`additionalProperties`:** `true` at every level. This matches the
Pydantic `model_config = {"extra": "allow"}` runtime behavior so project-
specific fields (`author_year`, `notes`, …) survive validation. v1 does
NOT tighten `additionalProperties: false` even under `--strict`; see
"Out of Scope" below.

### Checks (always-on under `dag validate`)

The following run unconditionally. Each produces `ValidationFinding`
entries with `severity="error"` and blocks exit 0:

| Rule id | Check | Implementation |
|---|---|---|
| `shape` | Pydantic model validation (shape + intra-record invariants). Includes the existing Phase 1 checks: id/source/target/description present, enum validity, (source,target) uniqueness within a file, eliminated↔eliminated_by coherence, posterior HDI↔beta coherence, ref-entry one-kind-tag rule. | Delegates to existing `EdgesYamlFile.model_validate()`. |
| `refs` | Per-entry ref resolution on disk. Task / interpretation / discussion / proposition / paper refs must resolve. DOI syntax + unknown accession format remain warn-only (preserved from Phase 1). | Delegates to existing `validate_ref_entry()`. |
| `topology_missing_in_yaml` | Every edge `a -> b` in `<slug>.dot` has a matching YAML record with `source=a`, `target=b`. | New. |
| `topology_missing_in_dot` | Every YAML record has a matching `.dot` edge. | New. |
| `topology_node_mismatch` | YAML `source` / `target` strings correspond to a node present in the `.dot`. | New. |
| `acyclicity` | The `.dot` topology is acyclic (DFS; reports one cycle with its node path). | New. |
| `posterior_finite` | `beta` is finite (not NaN / inf / -inf). | New. |
| `posterior_hdi_ordered` | When both present, `hdi_low ≤ hdi_high`. | New. |
| `posterior_prob_sign_range` | `prob_sign` ∈ [0, 1] when present. | New. |
| `jsonschema_conformance` | The raw YAML dict validates against the shipped `edges.schema.json` via the `jsonschema` library. Catches drift between Pydantic and the committed artifact; in practice its error list is almost always a subset of `shape`, so this check is primarily a tripwire for schema regeneration being forgotten. | New. |

### Checks (strict-only: `--strict`)

These produce `ValidationFinding` entries with `severity="strict_error"`
and block exit 0 only when `--strict` is passed:

| Rule id | Check |
|---|---|
| `identification_missing` | Every edge declares `identification:` explicitly (no implicit default, no `DeprecationWarning`). The Phase 1 DeprecationWarning-tolerant default remains the non-strict behavior. |
| `description_nonempty` | Every ref-entry `description` is a non-empty, non-whitespace-only string. (Pydantic currently requires `description`'s presence but accepts `""`.) |
| `dot_nodes_unused` | Every node in the `.dot` participates in at least one edge (no orphan nodes). |
| `cross_dag_node_consistency` | When a node name appears in ≥2 DAGs, it must appear with exact string equality (case-sensitive). Flags `prc2` in one file vs `PRC2` in another. |

Strict-only checks are appropriate to turn on in CI once a project has
completed Phase 1 backfill. They are deliberately permissive by default
so that in-progress migrations produce actionable, non-catastrophic
output.

### Data model

```python
@dataclass(frozen=True)
class ValidationFinding:
    dag: str                                     # DAG slug; "" for cross-DAG
    edge_id: int | None                          # None for file-level findings
    rule: str                                    # one of the rule ids above
    severity: Literal["error", "strict_error"]
    message: str                                 # human-readable
    location: str | None                         # e.g. "h1-prognosis.edges.yaml"

@dataclass(frozen=True)
class ValidationReport:
    today: date
    strict: bool
    findings: tuple[ValidationFinding, ...]

    @property
    def ok(self) -> bool:
        return not any(self._blocks(f) for f in self.findings)

    def _blocks(self, f: ValidationFinding) -> bool:
        return f.severity == "error" or (self.strict and f.severity == "strict_error")

    def to_json(self) -> dict: ...
```

Single linear finding list keeps the printer and the JSON contract
simple. Strict-only findings are emitted regardless of the flag so
`--json` output is self-describing (a downstream consumer can see that
strict-only issues exist without rerunning); the flag only gates exit
code and human-printer emphasis.

### CLI contract

**`dag validate`:**

- `--strict` — enable strict-only gates.
- `--dag <slug>` — scope to one DAG file; default is every DAG in the
  `dag_dir` (respecting the optional `dags:` whitelist in `science.yaml`).
- `--json` — stable machine-readable output. Schema:

  ```json
  {
    "today": "YYYY-MM-DD",
    "strict": false,
    "ok": true,
    "findings": [
      {
        "dag": "h1-prognosis",
        "edge_id": 5,
        "rule": "posterior_finite",
        "severity": "error",
        "message": "posterior.beta is not finite (got inf)",
        "location": "h1-prognosis.edges.yaml"
      }
    ]
  }
  ```

- Exit 0 if `report.ok`; exit 1 otherwise.

**`dag schema`:**

- `--output PATH` — write to this file; default is stdout.
- No `--strict` / `--dag` flags (the schema is project-independent).

**`dag audit` integration:**

- Implicitly runs `validate_project(paths, strict=audit_strict)` before
  `check_staleness(paths)`. `audit --strict` propagates to validate.
- `audit` JSON output gains a top-level `validation` key alongside the
  existing staleness sections:

  ```json
  {
    "today": "YYYY-MM-DD",
    "strict": false,
    "validation": { "ok": true, "findings": [] },
    "staleness": { ... existing shape ... },
    "mutations": []
  }
  ```

- `audit` exit code is the OR of validation exit code and staleness exit
  code (0 iff both are 0).
- `audit --fix` does NOT attempt to fix validation errors; validation
  failures block the audit mutation path with exit 1 and a clear
  "run `dag validate` first" message. Rationale: auto-fixing a topology
  mismatch is ambiguous (which side is truth — YAML or .dot?) and
  belongs to curation discretion, not a one-line mutation.

### File layout

```
science-tool/src/science_tool/dag/
    validate.py              # NEW — ValidationReport, ValidationFinding, validate_project()
    schema.py                # (existing; unchanged)
    refs.py                  # (existing; unchanged)
    render.py                # (existing; unchanged)
    number.py                # (existing; unchanged)
    staleness.py             # (existing; unchanged)
    audit.py                 # MODIFIED — composes validate + staleness
    cli.py                   # MODIFIED — register `validate` + `schema` subcommands
    init.py                  # (existing; unchanged)
    paths.py                 # (existing; unchanged)
    edges.schema.json        # NEW — generated artifact (committed)

science-tool/tests/dag/
    test_validate.py              # NEW — per-check unit tests
    test_validate_cli.py          # NEW — click runner: exit codes, --json, --strict, --dag
    test_schema_artifact.py       # NEW — drift guard: committed file == Pydantic emit
    test_audit.py                 # MODIFIED — verify audit composes validate findings
    fixtures/
        minimal/                  # (existing; extended with broken variants)
            edges-cyclic.yaml
            edges-cyclic.dot
            edges-yaml-dot-mismatch.yaml
            edges-bad-posterior.yaml
            edges-missing-identification.yaml
            edges-orphan-node.dot
            …
        mm30/                     # (existing; unchanged)
```

### `jsonschema` dependency

Adds `jsonschema>=4.0` as a runtime dependency. Currently absent from
`science-tool`'s pyproject; lean in — it's a small, well-maintained
package and the conformance check requires it. If future minimization
pressure arises, the `jsonschema_conformance` check could be dropped
(it's a tripwire, not a correctness gate) and the dependency removed.

## Migration — mm30 consuming the upstream

Same pattern as Phase 1:

1. Land this spec + plan in `science-tool`. No mm30 changes required
   initially — the new command just starts working the next time mm30
   bumps its `science-tool` pin.
2. Add a mm30 task `tNNN` to run `science-tool dag validate` on the
   current YAML and fix any (presumably rare) findings that surface.
3. Optionally, once the `identification:` backfill task lands, enable
   `science-tool dag validate --strict` in mm30's CI.
4. `/science:dag-audit` skill's default invocation now surfaces
   validation findings alongside staleness; no skill changes required
   because it already emits the `dag audit --json` output verbatim.

## Documentation

- `/mnt/ssd/Dropbox/science/references/dag-two-axis-evidence-model.md`
  (created in Phase 1) gets an additive section on "validate vs strict"
  — a short paragraph explaining that strict gates are opt-in migration
  completeness signals, not "the correct level of rigor."
- `commands/big-picture.md` already calls `dag audit` for read-only
  rollups; no change needed — validation findings flow through the
  existing JSON surface.

## Out of Scope

- Auto-fix of validation findings (`dag validate --fix`). Belongs under
  `dag audit --fix` if ever, and even then only for narrow mechanical
  fixes (regenerate schema artifact, add `identification: none` to
  edges that are missing it). Topology mismatches are not mechanical.
- Tightening `additionalProperties: false` under `--strict`. Projects
  currently rely on extra fields (`author_year`, `notes`); flipping this
  globally would break them. A future opt-in `--strict-extra` flag could
  cover this if typos survive in practice.
- Graph-layer validation (Phase 2b `sync-dag`).
- Editor / IDE schema distribution via a stable `$id` URL. The schema
  file is shipped as package data; picking a hosting story is a Phase 4
  concern.
- Cross-project ref systems (`task` in project A citing `task` in
  project B). Out-of-scope for the whole `dag` surface.
- A `dag validate --fix` option that regenerates the schema artifact on
  drift. The `dag schema --output` command covers this already; a
  `--fix` variant would be sugar with no new capability.

## Risks and Counter-Arguments

**"`jsonschema_conformance` duplicates `shape`."** Yes, partially. Its
value is catching the specific failure mode of "someone edited
schema.py but forgot to regenerate `edges.schema.json`" — a drift
signal that Pydantic-only validation cannot detect. If the drift test
is considered sufficient, this runtime check can be dropped.
Mitigation: keep it in v1; remove if it proves noisy.

**"Topology checks assume `.dot` is parseable."** The existing Phase 1
code doesn't parse `.dot` itself; it delegates to graphviz at render
time. Validate now needs an in-Python `.dot` parser for topology. The
implementation uses a narrow regex-based parser (mirroring the one in
`number.py` for edge attribute handling); `pydot` / `pygraphviz` are
heavier dependencies and not worth pulling in for this. Risk: an
unusual `.dot` construct that the regex doesn't handle produces a false
positive `topology_*` finding. Mitigation: start by reusing
`number.py`'s existing `EDGE_RE` and node-extraction logic — those are
already battle-tested against the mm30 fixture.

**"Strict-only checks will get ignored."** Plausible. The value of
`--strict` is exactly that it's not on by default: projects turn it on
when they're ready. Mitigation: document explicitly in
`references/dag-two-axis-evidence-model.md` and in mm30's migration
task.

**"Schema artifact drift test is brittle across Pydantic versions."**
Pydantic v2 minor versions can change JSON Schema emission details. If
upstream changes, the test fails and a regeneration is required. This
is intentional — we want to notice version-induced schema changes
before they hit downstream consumers. Mitigation: pin Pydantic's minor
version in `pyproject.toml` until the schema artifact story stabilizes.

## Acceptance Criteria

1. `science-tool dag validate` on the current mm30 fixture exits 0
   (shape + refs + topology + acyclicity + posterior + jsonschema all
   pass).
2. `science-tool dag validate --strict` on the same fixture exits 1 iff
   the fixture has any edge missing an explicit `identification:` (which
   the Phase 1 fixture does, per its `DeprecationWarning`-tolerant
   state).
3. `science-tool dag schema --output /tmp/x.json` emits valid draft-
   2020-12 JSON Schema; the committed
   `src/science_tool/dag/edges.schema.json` matches the generated
   output byte-for-byte under canonical serialization.
4. `dag audit` JSON output includes a `validation` section alongside
   `staleness`; exit code is the OR of the two.
5. All existing Phase 1 tests remain green (86/86).
6. Synthetic fixtures with (a) a cycle, (b) a YAML/dot topology
   mismatch, (c) `beta: inf`, (d) `hdi_low > hdi_high`, (e) `prob_sign:
   1.7`, (f) a dot edge absent from YAML each exit 1 with the expected
   `rule` in the `--json` output.
7. Synthetic fixtures with (a) an invalid DOI, (b) an unknown accession
   format each exit 0 — warn-only behavior preserved from Phase 1.
8. `test_schema_artifact.py` fails with an actionable message when the
   committed `edges.schema.json` drifts from `EdgesYamlFile.
   model_json_schema()`.

## Open Questions

- Should `dag validate` check that `source_dot:` in the edges YAML
  points at an existing `.dot` file? Pydantic currently makes the field
  optional and does not resolve paths. Lean **yes** — add a file-level
  finding `source_dot_missing` under the always-on set.
- Should the `jsonschema_conformance` check run *before* or *after*
  Pydantic `shape`? If before, Pydantic shape issues may surface twice
  (once as `jsonschema_conformance`, once as `shape`). If after,
  Pydantic filters most cases and `jsonschema_conformance` becomes the
  pure drift tripwire. Lean **after**.
- `source_dot` field, strict-only `dot_nodes_unused`, and any other
  `.dot`-level check: do we want a `source_dot_exists` precondition
  check that short-circuits the other topology checks when the `.dot`
  is missing? Lean **yes** — skipping is less noisy than cascading
  "node not found" findings.

## Summary

`science-tool dag validate` composes existing Phase 1 shape + ref
checks with new cross-file, acyclicity, posterior-sanity, and JSON-
Schema-conformance checks. `--strict` gates migration-completeness
signals (explicit identification, non-empty descriptions, no orphan
dot nodes, cross-DAG node-name consistency). `science-tool dag schema`
emits the generated JSON Schema for downstream consumers. `dag audit`
absorbs validate as a precondition, so CI and the `/science:dag-audit`
skill get validation findings for free.

Size: ~300 LOC new module (`validate.py`) + ~50 LOC audit modifications
+ ~30 LOC CLI wiring + ~200 LOC tests + the generated `edges.schema.
json` artifact. Single runtime dependency added (`jsonschema`).
