# Source Compiler — Slice C: Phased Compiler & Audit/Materialize Unification (Design)

**Spec:** Patchwork kernel **Spec 3 — Source Compiler & Identity Substrate**
(`~/d/science/docs/plans/2026-06-14-patchwork-kernel-architecture-design.md`).
This is the third and final keystone slice of Spec 3.

**Status:** Approved 2026-06-15.

## Goal

Make the local source compiler an explicit, ordered set of phases, and unify the
audit and materialization paths so the reference audit is a *shared phase* the two
entry points reuse — not a duplicated load-and-re-audit. Strictly behavior-neutral.

This closes two of the four Spec 3 "key decisions": **"split compiler phases"** and
**"unify audit and materialization."** (The other two — "replace adapter-name
branching" and "own the source-freshness record" — shipped as Slice A and Slice B.)

## Context

Spec 3 was decomposed keystone-first:

- **Slice A — Adapter Policy** (shipped): adapter load behavior is declared policy;
  no `isinstance`/`adapter.name ==` branching in the load loop.
- **Slice B — `SourceSnapshot` & freshness-origin** (shipped): content-derived
  freshness via persisted source snapshots.
- **Slice C — this design**: phased compiler + audit/materialize unification.

After C, Spec 3's substrate cleanup is complete; the remaining Spec 3 fill-outs
(`io.py` revision-manifest unification, snapshot hash perf, remote/DOI/Zenodo
sources) are explicitly **separate future specs**, not part of this slice.

## Scope

**In scope (refactor only, in `graph/materialize.py`):**

- An internal, typed `_compile()` orchestrator running ordered named phases.
- A shared audit phase consumed by both `materialize_graph` and
  `materialization_audit` (removes the duplicate load + audit).
- A real Emit/Derive split inside the build path.
- The three public entry points become thin projections, **signatures unchanged**.

**Out of scope (unchanged this slice):**

- `propagate_freshness_in_memory` — a separate sweep with its own gating; left
  untouched.
- No new `compiler/` package. If `materialize.py` later proves too large once the
  phases stabilize, extraction is a future mechanical move.
- The three Spec 3 fill-outs above.

## Current state (the problem)

`graph/materialize.py` exposes three public functions:

- `materialize_graph(project_root, *, strict=True) -> Path` — `science graph
  materialize` (cli.py:1213).
- `materialization_audit(project_root) -> tuple[list[dict], bool]` — `science graph
  audit` (cli.py:1289) **and** the `validate` graph check (validate/checks/graph.py:178).
- `build_dataset_from_sources(sources) -> Dataset` — `patch check` diagnostics
  (patch/cli.py:84). `propagate_freshness_in_memory` calls the private
  `_build_dataset_from_sources` directly.

Two structural problems:

1. **Duplicated front of the pipeline.** Both `materialize_graph` and
   `materialization_audit` independently call `load_project_sources(...)` and
   `audit_project_sources(...)`. The audit is a parallel re-derivation, not a
   shared phase.
2. **Undifferentiated build blob.** `_build_dataset_from_sources` is a ~117-line
   sequence with no named phase boundaries: base-graph emission and epistemic
   derivation are interleaved in one function, with the snapshot/`bears_on`
   ordering preserved only by a load-bearing comment.

## Design

### Phase model

The compiler pipeline is five ordered phases. All functions live in
`graph/materialize.py`.

| Phase | Function | Contract |
|---|---|---|
| Load | `load_project_sources` (existing) | `project_root → ProjectSources`. Called as `load_project_sources(project_root.resolve(), strict_identity=False)` — the **single** load call site. |
| Audit | `_audit_phase(sources) -> tuple[list[AuditRow], bool]` | Wraps `audit_project_sources`. The **single** audit call site. |
| Emit | `_emit_phase(sources) -> EmitResult` | Base authored graph **plus the build context Derive needs**: entity emission, relations, produced_by/dataset_usage/sub-cohort/dataset-resource edges, authored relations, bindings, and `_validate_no_amendment_cycles`; constructs `kind_class` (`_classify_entities`) and `pre_registration_targets` (`_pre_registration_commitment_targets`, which depends on the emit-time `resolver` + `entity_index`). Returns `EmitResult(dataset, kind_class, pre_registration_targets)`. |
| Derive | `_derive_phase(emit, *, sources, source_snapshots)` | Epistemic layers in the existing load-bearing order: snapshot-layer emission → `_derive_bears_on_layer` (consumes `emit.kind_class` + `emit.pre_registration_targets`) → `_derive_patch_membership_layer` → dataset-independence → freshness (consumes `emit.kind_class` via `_build_entity_meta`). Mutates `emit.dataset`. |
| Write | `_write_phase(dataset, trig_path) -> Path` | `save_graph_dataset`, returns the path. |

`load_project_sources` is reused as-is (it already *is* the load phase). The new
phase functions are `_audit_phase`, `_emit_phase`, `_derive_phase`, `_write_phase`.

### Project-root preflight (materialize-only, outside `stop_after`)

The existing strict data-package migration scan is **not** a phase. It is a
project-root, materialize-only preflight gate (filesystem-dependent: it scans
`doc/data-packages/`). It runs **only** on the materialize path, exactly as today,
where `materialization_audit` never performs it. It is intentionally kept outside
the `stop_after` enumeration so no `stop_after="preflight"` or audit-preflight
semantics are implied.

### Orchestrator

```python
@dataclass(frozen=True)
class CompilationResult:
    sources: ProjectSources
    audit_rows: list[AuditRow]
    has_failures: bool
    dataset: Dataset | None        # None for stop_after="audit"
    trig_path: Path | None         # None for stop_after="audit"


def _compile(
    project_root: Path,
    *,
    stop_after: Literal["audit"] | None = None,
    strict: bool = True,
) -> CompilationResult:
    project_root = project_root.resolve()

    # Project-root preflight, materialize-only: runs only when producing output.
    if stop_after is None and strict:
        _preflight_migration(project_root)

    sources = load_project_sources(project_root, strict_identity=False)
    audit_rows, has_failures = _audit_phase(sources)

    if stop_after == "audit":
        # Audit-only: surface rows, never raise, never write.
        return CompilationResult(
            sources=sources,
            audit_rows=audit_rows,
            has_failures=has_failures,
            dataset=None,
            trig_path=None,
        )

    # Materialize path: hard audit gate (preserves the current ValueError).
    if has_failures:
        details = "; ".join(
            f"{row['source']} {row['field']} -> {row['target']}"
            for row in audit_rows
            if row["status"] == "fail"
        )
        raise ValueError(
            f"Cannot materialize graph with unresolved references: {details}"
        )

    trig_path = project_root / DEFAULT_GRAPH_PATH
    snapshots = compute_source_snapshots(
        sources, prior_graph_path=trig_path, today=_date.today()
    )
    dataset = _build_dataset_from_sources(sources, source_snapshots=snapshots)
    trig_path.parent.mkdir(parents=True, exist_ok=True)
    trig_path = _write_phase(dataset, trig_path)

    return CompilationResult(
        sources=sources,
        audit_rows=audit_rows,
        has_failures=has_failures,
        dataset=dataset,
        trig_path=trig_path,
    )
```

Notes:

- The `stop_after="audit"` branch uses the **same** load options
  (`load_project_sources(project_root.resolve(), strict_identity=False)`) as
  today's `materialization_audit` — this is part of the behavior-neutral contract.
- The snapshot-observation comment from `materialize_graph` (snapshots run
  unconditionally on the materialize path, not gated on `freshness_enabled`) is
  preserved at the `compute_source_snapshots` call.

### Public functions become thin projections (signatures unchanged)

```python
def materialize_graph(project_root: Path, *, strict: bool = True) -> Path:
    result = _compile(project_root, strict=strict)
    return result.trig_path  # never None on this path


def materialization_audit(project_root: Path) -> tuple[list[dict[str, str]], bool]:
    result = _compile(project_root, stop_after="audit")
    audit_rows = [
        {
            "check": row["check"],
            "status": row["status"],
            "source": row["source"],
            "field": row["field"],
            "target": row["target"],
            "details": row["details"],
        }
        for row in result.audit_rows
    ]
    return audit_rows, result.has_failures


def build_dataset_from_sources(sources: ProjectSources) -> Dataset:
    """Public wrapper for diagnostic re-derivation (e.g. `patch check`).

    Load/audit-free: composes Emit + Derive over already-loaded sources. Stays
    out of `_compile`.
    """
    return _build_dataset_from_sources(sources)
```

The `AuditRow → dict` mapping stays at the `materialization_audit` boundary;
`CompilationResult` carries typed `AuditRow`s internally.

### Emit/Derive split inside `_build_dataset_from_sources`

`_build_dataset_from_sources(sources, *, source_snapshots=None)` is refactored to
compose the two new phase functions, making the split real while keeping the public
`build_dataset_from_sources` projection spanning both:

```python
@dataclass(frozen=True)
class EmitResult:
    dataset: Dataset
    kind_class: dict[str, EntityClass]
    pre_registration_targets: set[URIRef]


def _build_dataset_from_sources(sources, *, source_snapshots=None) -> Dataset:
    emit = _emit_phase(sources)
    _derive_phase(emit, sources=sources, source_snapshots=source_snapshots)
    return emit.dataset
```

- `_emit_phase` owns dataset/named-graph setup, resolver/index construction, all
  base-graph emission through `_validate_no_amendment_cycles`, and computation of
  `kind_class` (`_classify_entities`) and `pre_registration_targets`
  (`_pre_registration_commitment_targets`, built from the emit-time `resolver` +
  `entity_index`). It returns these in `EmitResult` so Derive consumes them
  without recomputation — the phase boundary carries the build context forward.
- `_derive_phase` owns the snapshot-layer emission and the epistemic derivations,
  reading `emit.dataset`, `emit.kind_class`, and `emit.pre_registration_targets`
  and preserving the load-bearing ordering (snapshot layer emitted before
  `_derive_bears_on_layer`; `source_changes` threaded into the freshness layer;
  the `if sources.freshness_enabled` gate unchanged).

This keeps `propagate_freshness_in_memory`'s existing call
(`_build_dataset_from_sources(sources, source_snapshots=snapshots)`) working
verbatim — no change to that sweep.

## Behavior-neutral contract

The refactor must not change any output or observable behavior:

1. `materialize_graph` produces a graph-isomorphic `graph.trig` for a fixture
   project (byte-identical under deterministic serialization).
2. `materialization_audit` returns identical rows (dict shape and order) and
   `has_failures` flag.
3. The materialize path still raises the **exact** `ValueError` message on
   unresolved references, before any emit/derive/write.
4. The audit-only path does **not** raise on audit failures, does **not** run the
   project-root preflight, and does **not** write `graph.trig`.
5. `build_dataset_from_sources(sources)` performs no load and no audit.
6. The strict data-package preflight still raises its `RuntimeError` for
   unmigrated packages on the materialize path, and is absent on the audit path.

## Testing

Mirrors Slice A/B discipline (characterization + structural guard):

- **Characterization:** freeze `graph.trig` (knowledge + provenance + derived
  layers) for a fixture exercising entities, relations, snapshots, and freshness;
  assert equality before vs after the refactor (capture authored before the flip).
- **Audit parity:** `materialization_audit` rows + flag equal to a frozen capture
  for both a clean fixture and one with an unresolved reference.
- **Materialize gate:** unresolved reference → `materialize_graph` raises the exact
  `ValueError`; audit-only path returns `has_failures=True` without raising and
  writes nothing.
- **Preflight parity:** unmigrated data-package → `materialize_graph` raises
  `RuntimeError`; `materialization_audit` does not.
- **Emit/Derive split:** `build_dataset_from_sources(sources)` yields a dataset
  graph-isomorphic to the pre-refactor result (no load/audit performed).
- **Structural guard:** assert `graph/materialize.py` contains exactly **one**
  `load_project_sources(` call site and exactly **one** `audit_project_sources(`
  call site — proving the duplication is gone. Scoped to `graph/materialize.py`
  so unrelated callers elsewhere do not matter (mirrors Slice A's no-branching
  guard).

## File structure

All changes are within `graph/materialize.py`:

- **Add:** `CompilationResult` and `EmitResult` dataclasses; `_compile`,
  `_preflight_migration`, `_audit_phase`, `_emit_phase`, `_derive_phase`,
  `_write_phase`.
- **Rewrite (thin):** `materialize_graph`, `materialization_audit`.
- **Refactor (compose phases):** `_build_dataset_from_sources`.
- **Unchanged:** `build_dataset_from_sources`, all `_add_*` / `_derive_*` emission
  helpers, `load_project_sources`, `audit_project_sources`,
  `propagate_freshness_in_memory`.

No new modules, no moved code across files, no import churn in callers.
