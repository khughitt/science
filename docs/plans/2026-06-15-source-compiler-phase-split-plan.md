# Source Compiler Slice C — Phased Compiler & Audit/Materialize Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `graph/materialize.py` so the local source compiler runs explicit named phases (Load → Audit → Emit → Derive → Write) and the audit and materialize entry points share one `_compile()` orchestrator instead of independently re-loading and re-auditing.

**Architecture:** One internal `_compile(project_root, *, stop_after, strict) -> CompilationResult` runs the ordered phases; the three public functions (`materialize_graph`, `materialization_audit`, `build_dataset_from_sources`) become thin projections with unchanged signatures. The build body splits into `_emit_phase` (base authored graph + build context) and `_derive_phase` (snapshot + epistemic layers), carried across the boundary by a typed `EmitResult`. Strictly behavior-neutral.

**Tech Stack:** Python 3.13, rdflib, pytest. Repo is a uv workspace; run tools via `rtk proxy uv run --frozen ...` and git via `rtk git ...`. Work happens in the worktree `~/d/science/.worktrees/source-compiler-slice-c` on branch `feat/source-compiler-slice-c`.

**Spec:** `~/d/science/docs/plans/2026-06-15-source-compiler-phase-split-design.md`

---

## Conventions for every task

- **Worktree discipline:** every subagent MUST `cd` into the worktree and verify the branch before editing or committing:
  ```bash
  cd ~/d/science/.worktrees/source-compiler-slice-c
  rtk git branch --show-current   # MUST print: feat/source-compiler-slice-c
  ```
  If the branch is wrong, STOP — do not edit or commit (commits would leak to `main`).
- **Tests:** `rtk proxy uv run --frozen pytest <path> -v` (rtk has no `uv`/`pytest` subcommand; `rtk proxy` passes the raw command through). Run from the worktree root.
- **Commits:** `rtk git add <paths>` then `rtk git commit -m "<msg>"`. Do NOT include any `Co-Authored-By` trailer.
- **Behavior-neutral bar:** the existing emission suites (`tests/test_graph_materialize.py`, `tests/test_dataset_usage_materialize.py`, `tests/test_freshness_derivation.py`, `tests/graph/test_patch_membership_materialize.py`, `tests/test_source_snapshot_freshness_e2e.py`, etc.) are the comprehensive regression net for emitted-graph content. Each task must keep them green; do not modify them.

## File structure

All production changes are confined to one file:

- **Modify:** `science/src/science_tool/graph/materialize.py`
  - Add imports: `from dataclasses import dataclass`, `from typing import Literal`, and `AuditRow` to the existing `science_tool.graph.migrate` import.
  - Add types: `EmitResult`, `CompilationResult`.
  - Add functions: `_emit_phase`, `_derive_phase`, `_preflight_migration`, `_audit_phase`, `_write_phase`, `_compile`.
  - Refactor: `_build_dataset_from_sources` (compose the two phases), `materialize_graph`, `materialization_audit` (thin projections).
  - Unchanged: `build_dataset_from_sources`, every `_add_*` / `_derive_*` emission helper, `load_project_sources`, `audit_project_sources`, `propagate_freshness_in_memory`.

New test files:

- **Create:** `science/tests/graph/test_phase_split_contracts.py` (Task 1 safety net)
- **Create:** `science/tests/graph/test_phase_split_emit_derive.py` (Task 2 driver)
- **Create:** `science/tests/graph/test_phase_split_compile.py` (Task 3 drivers)

---

## Task 1: Behavior-neutral safety net (passes against current code)

This task adds protective pins that characterize *current* behavior and must stay green through Tasks 2–3. Unlike normal TDD, these tests pass immediately — they are the refactor safety net, authored before the refactor so regressions in Tasks 2–3 are caught instantly.

**Files:**
- Create: `science/tests/graph/test_phase_split_contracts.py`

- [ ] **Step 1: Write the safety-net tests**

```python
"""Behavior-neutral contract pins for the Spec 3 Slice C compiler refactor.

These pass against the current code and must remain green through the phase
split and audit/materialize unification. They lock the public contracts the
refactor must preserve: the materialize-only project-root preflight, the audit
hard-gate on the materialize path, the non-raising audit-only path, and the
load/audit-free `build_dataset_from_sources`.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from rdflib import Dataset

from science_tool.graph.materialize import (
    build_dataset_from_sources,
    materialization_audit,
    materialize_graph,
)
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS
from science_tool.graph.io import entity_uri_for_ref


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"), encoding="utf-8")


_SEED = "name: proj\nprofile: research\nprofiles: {local: local}\n"


def _question(root: Path, filename: str, cid: str) -> None:
    _write(
        root / "entities" / "questions" / filename,
        f'---\nid: "{cid}"\ntype: "question"\ntitle: "{cid}"\n---\n',
    )


def _build_dup_project(root: Path) -> None:
    """Two non-deprecated owners of one id → genuine audit failure (§B1)."""
    _write(root / "science.yaml", _SEED)
    _question(root, "q1.md", "question:q1")
    _question(root, "q1-dup.md", "question:q1")


def _build_unmigrated_dp_project(root: Path) -> None:
    """Valid manifest + one active (unmigrated) data-package → preflight target."""
    _write(root / "science.yaml", _SEED)
    _question(root, "q1.md", "question:q1")
    _write(
        root / "doc" / "data-packages" / "u.md",
        '---\nid: "data-package:u"\ntype: "data-package"\ntitle: "U"\nstatus: "active"\n---\n',
    )


def _build_clean_project(root: Path) -> Path:
    """Minimal project that materializes cleanly with freshness + snapshots."""
    demo = root / "demo"
    _write(demo / "science.yaml", "name: demo\nknowledge_profiles:\n  local: core\n")
    _write(demo / "knowledge" / "graph.trig", "")
    _write(
        demo / "entities" / "hypotheses" / "h1.md",
        """
        ---
        id: "hypothesis:h1"
        kind: "hypothesis"
        title: "Demo hypothesis"
        last_reviewed: "2026-05-01"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Original body.
        """,
    )
    return demo


def test_materialize_raises_on_audit_failure(tmp_path: Path) -> None:
    _build_dup_project(tmp_path)
    with pytest.raises(ValueError, match="Cannot materialize graph with unresolved references"):
        materialize_graph(tmp_path, strict=True)


def test_audit_only_path_does_not_raise_or_write(tmp_path: Path) -> None:
    _build_dup_project(tmp_path)
    rows, has_failures = materialization_audit(tmp_path)  # must NOT raise
    assert has_failures is True
    assert any(r["status"] == "fail" for r in rows)
    # audit writes nothing
    assert not (tmp_path / "knowledge" / "graph.trig").exists()


def test_preflight_is_materialize_only(tmp_path: Path) -> None:
    _build_unmigrated_dp_project(tmp_path)
    # materialize path runs the preflight and raises RuntimeError
    with pytest.raises(RuntimeError) as exc:
        materialize_graph(tmp_path, strict=True)
    assert "data-package:u" in str(exc.value)
    assert "data-package migrate" in str(exc.value)
    # audit path skips the preflight: it must not raise RuntimeError
    rows, has_failures = materialization_audit(tmp_path)
    assert isinstance(rows, list)


def test_build_dataset_from_sources_is_load_audit_free(tmp_path: Path) -> None:
    root = _build_clean_project(tmp_path)
    sources = load_project_sources(root, strict_identity=False)
    # delete the pre-seeded graph.trig to prove build_dataset_from_sources writes nothing
    (root / "knowledge" / "graph.trig").unlink()

    ds = build_dataset_from_sources(sources)

    assert isinstance(ds, Dataset)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    h1 = entity_uri_for_ref("hypothesis:h1")
    assert (h1, None, None) in knowledge  # entity emitted
    # build_dataset_from_sources does no filesystem write
    assert not (root / "knowledge" / "graph.trig").exists()
```

- [ ] **Step 2: Run the safety net to verify it PASSES against current code**

Run: `rtk proxy uv run --frozen pytest tests/graph/test_phase_split_contracts.py -v`
Expected: 4 passed. (These characterize current behavior; if any fails, the fixture is wrong — fix the test before proceeding, do not change production code.)

- [ ] **Step 3: Commit**

```bash
rtk git add tests/graph/test_phase_split_contracts.py
rtk git commit -m "test(source-compiler): Slice C behavior-neutral safety net (preflight/audit-gate/build-dataset contracts)"
```

---

## Task 2: Emit/Derive split via `EmitResult`

Split the build body into `_emit_phase` (base authored graph + build context) and `_derive_phase` (snapshot + epistemic layers), carried by a typed `EmitResult`, and refactor `_build_dataset_from_sources` to compose them. Behavior-neutral.

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py`
- Create/extend: `science/tests/graph/test_phase_split_emit_derive.py`

- [ ] **Step 1: Write the failing test**

```python
"""Drives the Emit/Derive phase split (Slice C)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from rdflib import Dataset

from science_tool.graph.materialize import EmitResult, _emit_phase
from science_tool.graph.sources import load_project_sources


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"), encoding="utf-8")


def _clean(root: Path) -> Path:
    demo = root / "demo"
    _write(demo / "science.yaml", "name: demo\nknowledge_profiles:\n  local: core\n")
    _write(demo / "knowledge" / "graph.trig", "")
    _write(
        demo / "entities" / "hypotheses" / "h1.md",
        """
        ---
        id: "hypothesis:h1"
        kind: "hypothesis"
        title: "Demo hypothesis"
        last_reviewed: "2026-05-01"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Original body.
        """,
    )
    return demo


def test_emit_phase_returns_build_context(tmp_path: Path) -> None:
    root = _clean(tmp_path)
    sources = load_project_sources(root, strict_identity=False)

    emit = _emit_phase(sources)

    assert isinstance(emit, EmitResult)
    assert isinstance(emit.dataset, Dataset)
    # Build context Derive needs is carried forward, not recomputed.
    assert isinstance(emit.kind_class, dict)
    assert isinstance(emit.pre_registration_targets, dict)
    # Base graph already emitted (entity present before any derive step).
    from science_tool.graph.io import entity_uri_for_ref
    from science_tool.graph.store import PROJECT_NS

    knowledge = emit.dataset.graph(PROJECT_NS["graph/knowledge"])
    assert (entity_uri_for_ref("hypothesis:h1"), None, None) in knowledge
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk proxy uv run --frozen pytest tests/graph/test_phase_split_emit_derive.py -v`
Expected: FAIL with `ImportError: cannot import name 'EmitResult'` (and `_emit_phase`).

- [ ] **Step 3: Add the `dataclass` import**

In `science/src/science_tool/graph/materialize.py`, add to the top import block (after `from __future__ import annotations`):

```python
from dataclasses import dataclass
```

- [ ] **Step 4: Add `EmitResult` and the two phase functions; refactor `_build_dataset_from_sources`**

Replace the entire current body of `_build_dataset_from_sources` (the function starting `def _build_dataset_from_sources(` through its `return dataset`) with the following three definitions. Place `EmitResult` immediately above `_build_dataset_from_sources`:

```python
@dataclass(frozen=True)
class EmitResult:
    """Output of the Emit phase: the base authored graph plus the build context
    the Derive phase consumes (so Derive never recomputes `kind_class` or
    `pre_registration_targets`)."""

    dataset: Dataset
    kind_class: dict[str, EntityClass]
    pre_registration_targets: dict[URIRef, list[URIRef]]


def _emit_phase(sources: ProjectSources) -> EmitResult:
    """Emit the base authored graph and build the context Derive consumes.

    Owns dataset/named-graph setup, resolver/index construction, all base-graph
    emission through `_validate_no_amendment_cycles`, and the `kind_class` /
    `pre_registration_targets` build context.
    """
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    bridge = dataset.graph(PROJECT_NS["graph/bridge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    dataset.graph(PROJECT_NS["graph/causal"])
    datasets = dataset.graph(PROJECT_NS["graph/datasets"])

    resolver = ReferenceResolver.from_entities(
        sources.entities, manual_aliases=sources.manual_aliases, identity_table=build_identity_table(sources)
    )
    entity_index = {entity.canonical_id: entity for entity in sources.entities}
    ext_prefixes = _EXTERNAL_PREFIXES | external_prefixes(sources.ontology_catalogs)
    external_reference_ids = {
        d.canonical_id
        for d in sources.identity_declarations
        if d.participation_mode == ParticipationMode.EXTERNAL_REFERENCE
    }

    for entity in sources.entities:
        _add_entity(
            entity=entity,
            knowledge=knowledge,
            provenance=provenance,
            overlay_paths=sources.commons_overlay_paths,
            external_reference_ids=external_reference_ids,
        )

    for entity in sources.entities:
        _add_relations(
            entity,
            entity_index=entity_index,
            resolver=resolver,
            knowledge=knowledge,
            bridge=bridge,
            provenance=provenance,
            ontology_catalogs=sources.ontology_catalogs,
            ext_prefixes=ext_prefixes,
        )

    _add_produced_by_edges(sources, entity_index=entity_index, knowledge=knowledge)
    _add_dataset_usage_edges(sources, resolver=resolver, provenance=provenance)
    _add_sub_cohort_edges(sources, resolver=resolver, knowledge=knowledge)
    _add_dataset_resource_edges(sources, datasets=datasets)

    kind_class = _classify_entities(sources)
    pre_registration_targets = _pre_registration_commitment_targets(
        sources,
        entity_index=entity_index,
        resolver=resolver,
    )

    for relation in sources.relations:
        _add_authored_relation(
            relation,
            dataset=dataset,
            entity_index=entity_index,
            resolver=resolver,
            bridge=bridge,
            ontology_catalogs=sources.ontology_catalogs,
            ext_prefixes=ext_prefixes,
            kind_class=kind_class,
        )

    for binding in sources.bindings:
        _add_binding(
            binding,
            knowledge=knowledge,
            provenance=provenance,
            entity_index=entity_index,
            resolver=resolver,
        )

    _validate_no_amendment_cycles(dataset)

    return EmitResult(
        dataset=dataset,
        kind_class=kind_class,
        pre_registration_targets=pre_registration_targets,
    )


def _derive_phase(
    emit: EmitResult,
    *,
    sources: ProjectSources,
    source_snapshots: SourceSnapshotResult | None,
) -> None:
    """Emit the snapshot layer and derive the epistemic layers onto `emit.dataset`.

    Preserves the load-bearing ordering: snapshot layer before `_derive_bears_on_layer`
    (so each SourceSnapshot's `bears_on` edge exists for closure); `source_changes`
    threaded into the freshness layer; the `freshness_enabled` gate intact.
    """
    dataset = emit.dataset
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    if source_snapshots is not None:
        emit_source_snapshots(dataset, source_snapshots)

    _derive_bears_on_layer(
        dataset,
        kind_class=emit.kind_class,
        pre_registration_targets=emit.pre_registration_targets,
        eligible_code_files=_eligible_code_files(sources),
    )
    _derive_patch_membership_layer(dataset, sources=sources)
    emit_dataset_independence_records(
        provenance,
        derive_dataset_independence_records(knowledge, provenance),
    )
    if sources.freshness_enabled:
        entity_meta = _build_entity_meta(sources, emit.kind_class)
        source_changes = source_snapshots.source_changes if source_snapshots is not None else {}
        _derive_freshness_layer(
            dataset, entities=entity_meta, today=_date.today(), source_changes=source_changes
        )


def _build_dataset_from_sources(
    sources: ProjectSources, *, source_snapshots: SourceSnapshotResult | None = None
) -> Dataset:
    """Build the in-memory rdflib Dataset that `materialize_graph` would write.

    Composes the Emit phase (`_emit_phase`) and the Derive phase (`_derive_phase`).
    Pure: takes `ProjectSources`, returns a populated `Dataset`, never touches the
    filesystem. When `source_snapshots` is provided, the snapshot layer is emitted
    ahead of `_derive_bears_on_layer`; when None, no snapshot layer is emitted
    (pre-Slice-B behavior). Used by both `materialize_graph` (writes to disk) and
    the `propagate_freshness_in_memory` sweep (discards the dataset).
    """
    emit = _emit_phase(sources)
    _derive_phase(emit, sources=sources, source_snapshots=source_snapshots)
    return emit.dataset
```

- [ ] **Step 5: Run the driver test to verify it passes**

Run: `rtk proxy uv run --frozen pytest tests/graph/test_phase_split_emit_derive.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Run the safety net and the emission regression suites**

Run:
```bash
rtk proxy uv run --frozen pytest \
  tests/graph/test_phase_split_contracts.py \
  tests/test_graph_materialize.py \
  tests/test_dataset_usage_materialize.py \
  tests/test_freshness_derivation.py \
  tests/graph/test_patch_membership_materialize.py \
  tests/test_source_snapshot_freshness_e2e.py -q
```
Expected: all passed (behavior-neutral — the split changed no emission logic).

- [ ] **Step 7: Commit**

```bash
rtk git add science/src/science_tool/graph/materialize.py tests/graph/test_phase_split_emit_derive.py
rtk git commit -m "refactor(source-compiler): split build into _emit_phase/_derive_phase via EmitResult (Slice C)"
```

---

## Task 3: Unify audit and materialize via `_compile` + thin wrappers

Introduce `CompilationResult`, the phase helpers (`_preflight_migration`, `_audit_phase`, `_write_phase`), and the `_compile` orchestrator; rewrite `materialize_graph` and `materialization_audit` as thin projections so the load + audit duplication is removed.

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py`
- Create: `science/tests/graph/test_phase_split_compile.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Drives the audit/materialize unification (Slice C): single _compile pipeline."""

from __future__ import annotations

import inspect
from datetime import date
from pathlib import Path
from textwrap import dedent

from rdflib import Dataset

import science_tool.graph.materialize as m
from science_tool.graph.materialize import (
    CompilationResult,
    _build_dataset_from_sources,
    _compile,
    materialize_graph,
)
from science_tool.graph.source_snapshots import compute_source_snapshots
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import DEFAULT_GRAPH_PATH, PROJECT_NS


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"), encoding="utf-8")


def _clean(root: Path) -> Path:
    demo = root / "demo"
    _write(demo / "science.yaml", "name: demo\nknowledge_profiles:\n  local: core\n")
    _write(demo / "knowledge" / "graph.trig", "")
    _write(
        demo / "entities" / "hypotheses" / "h1.md",
        """
        ---
        id: "hypothesis:h1"
        kind: "hypothesis"
        title: "Demo hypothesis"
        last_reviewed: "2026-05-01"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Original body.
        """,
    )
    return demo


# The named graphs the compiler writes. The clean fixture has no patch
# definitions, so it produces no patch named graphs — these five are complete.
_GRAPH_NAMES = ("graph/knowledge", "graph/bridge", "graph/provenance", "graph/causal", "graph/datasets")


def _quads(ds: Dataset) -> set[tuple[str, str, str, str]]:
    out: set[tuple[str, str, str, str]] = set()
    for name in _GRAPH_NAMES:
        g = ds.graph(PROJECT_NS[name])
        for s, p, o in g:
            out.add((str(s), str(p), str(o), name))
    return out


def _load(path: Path) -> Dataset:
    ds = Dataset()
    ds.parse(source=str(path), format="trig")
    return ds


def test_single_load_and_audit_call_sites() -> None:
    """The unification: exactly one load and one audit call site in materialize.py."""
    src = inspect.getsource(m)
    assert src.count("load_project_sources(") == 1
    assert src.count("audit_project_sources(") == 1


def test_compile_stop_after_audit_does_not_write(tmp_path: Path) -> None:
    root = _clean(tmp_path)
    result = _compile(root, stop_after="audit")

    assert isinstance(result, CompilationResult)
    assert result.dataset is None
    assert result.trig_path is None
    assert result.has_failures is False
    # audit-only writes nothing: the pre-seeded empty graph.trig is untouched.
    assert (root / DEFAULT_GRAPH_PATH).read_text() == ""


def test_materialize_write_path_matches_pure_build(tmp_path: Path) -> None:
    """The orchestrator's emit/derive/write output equals the pure build path."""
    root = _clean(tmp_path)
    sources = load_project_sources(root, strict_identity=False)
    # Compute expected FIRST, while graph.trig is still empty (same baseline the
    # materialize path will see, since the pure build writes nothing).
    snaps = compute_source_snapshots(sources, prior_graph_path=root / DEFAULT_GRAPH_PATH, today=date.today())
    expected = _quads(_build_dataset_from_sources(sources, source_snapshots=snaps))

    actual_path = materialize_graph(root, strict=False)
    actual = _quads(_load(actual_path))

    assert actual == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rtk proxy uv run --frozen pytest tests/graph/test_phase_split_compile.py -v`
Expected: FAIL — `ImportError: cannot import name 'CompilationResult'` / `_compile`, and `test_single_load_and_audit_call_sites` would fail with count 2 != 1 once imports resolve.

- [ ] **Step 3: Add the remaining imports**

In `science/src/science_tool/graph/materialize.py`:

Add to the typing imports near the top:
```python
from typing import Literal
```

Change the existing migrate import line:
```python
from science_tool.graph.migrate import audit_project_sources
```
to:
```python
from science_tool.graph.migrate import AuditRow, audit_project_sources
```

- [ ] **Step 4: Add `CompilationResult` and the phase helpers**

Add these definitions to `materialize.py` (place `CompilationResult` next to `EmitResult`; the helper functions can go just above `materialize_graph`):

```python
@dataclass(frozen=True)
class CompilationResult:
    """Output of the compiler pipeline. `dataset`/`trig_path` are None for an
    audit-only run (`stop_after="audit"`)."""

    sources: ProjectSources
    audit_rows: list[AuditRow]
    has_failures: bool
    dataset: Dataset | None
    trig_path: Path | None


def _preflight_migration(project_root: Path) -> None:
    """Project-root preflight, materialize-only: block on unmigrated data-packages.

    Scans `doc/data-packages/` for active (non-superseded) legacy data-package
    entities and raises RuntimeError if any remain. Not a phase and outside
    `stop_after`: the audit path never runs this.
    """
    from science_model.frontmatter import parse_frontmatter

    unmigrated: list[str] = []
    dp_dir = project_root / "doc" / "data-packages"
    if dp_dir.exists():
        for md in dp_dir.rglob("*.md"):
            result = parse_frontmatter(md)
            fm = result[0] if result else {}
            if fm.get("type") == "data-package" and fm.get("status") != "superseded":
                unmigrated.append(str(fm.get("id", md.stem)))
    if unmigrated:
        slugs = ", ".join(sorted(unmigrated))
        raise RuntimeError(
            f"unmigrated data-package entities: {slugs}. "
            f"Run `science data-package migrate <slug>` to split each into "
            f"derived dataset(s) + research-package."
        )


def _audit_phase(sources: ProjectSources) -> tuple[list[AuditRow], bool]:
    """Audit phase: the single `audit_project_sources` call site."""
    return audit_project_sources(sources)


def _write_phase(dataset: Dataset, trig_path: Path) -> Path:
    """Write phase: persist the dataset to `trig_path`."""
    trig_path.parent.mkdir(parents=True, exist_ok=True)
    save_graph_dataset(dataset, trig_path)
    return trig_path


def _compile(
    project_root: Path,
    *,
    stop_after: Literal["audit"] | None = None,
    strict: bool = True,
) -> CompilationResult:
    """Run the source-compiler phases: Load -> Audit -> Emit -> Derive -> Write.

    `stop_after="audit"` returns after the audit phase without gating, emitting,
    or writing (the `materialization_audit` projection). A full run hard-gates on
    audit failures (the `materialize_graph` projection). The project-root preflight
    is materialize-only and lives outside `stop_after`.
    """
    project_root = project_root.resolve()

    # Project-root preflight, materialize-only: only when producing output.
    if stop_after is None and strict:
        _preflight_migration(project_root)

    sources = load_project_sources(project_root, strict_identity=False)
    audit_rows, has_failures = _audit_phase(sources)

    if stop_after == "audit":
        return CompilationResult(
            sources=sources,
            audit_rows=audit_rows,
            has_failures=has_failures,
            dataset=None,
            trig_path=None,
        )

    if has_failures:
        details = "; ".join(
            f"{row['source']} {row['field']} -> {row['target']}"
            for row in audit_rows
            if row["status"] == "fail"
        )
        raise ValueError(f"Cannot materialize graph with unresolved references: {details}")

    trig_path = project_root / DEFAULT_GRAPH_PATH
    # Snapshot OBSERVATION is compiler/provenance state and runs UNCONDITIONALLY — it is not
    # gated on freshness_enabled. Gating it would stop persisting SourceSnapshot provenance
    # when freshness is off and lose baseline continuity, so re-enabling freshness later would
    # miss every intervening content change. Only the freshness-STATE derivation (inside
    # `_derive_phase`, the `if sources.freshness_enabled` block) is gated.
    snapshots = compute_source_snapshots(sources, prior_graph_path=trig_path, today=_date.today())
    dataset = _build_dataset_from_sources(sources, source_snapshots=snapshots)
    trig_path = _write_phase(dataset, trig_path)

    return CompilationResult(
        sources=sources,
        audit_rows=audit_rows,
        has_failures=has_failures,
        dataset=dataset,
        trig_path=trig_path,
    )
```

- [ ] **Step 5: Rewrite `materialize_graph` and `materialization_audit` as thin projections**

Replace the entire current bodies of `materialize_graph` and `materialization_audit` with:

```python
def materialize_graph(project_root: Path, *, strict: bool = True) -> Path:
    """Build `knowledge/graph.trig` deterministically from project sources.

    When `strict=True` (the default), the project-root preflight raises
    RuntimeError if any legacy data-package entities have not yet been migrated
    via `science data-package migrate`.
    """
    result = _compile(project_root, strict=strict)
    assert result.trig_path is not None  # a full compile always writes
    return result.trig_path


def materialization_audit(project_root: Path) -> tuple[list[dict[str, str]], bool]:
    """Audit a project root for unresolved canonical references."""
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
```

- [ ] **Step 6: Run the driver tests to verify they pass**

Run: `rtk proxy uv run --frozen pytest tests/graph/test_phase_split_compile.py -v`
Expected: PASS (3 passed) — including the single-call-site guard now reading 1 and 1.

- [ ] **Step 7: Run the safety net and the audit/materialize/CLI regression suites**

Run:
```bash
rtk proxy uv run --frozen pytest \
  tests/graph/test_phase_split_contracts.py \
  tests/graph/test_phase_split_emit_derive.py \
  tests/test_graph_materialize.py \
  tests/test_graph_build_strict.py \
  tests/test_source_snapshot_freshness_e2e.py \
  tests/test_graph_propagate_freshness_cli.py -q
```
Expected: all passed.

- [ ] **Step 8: Run the full suite (final behavior-neutral confirmation)**

Run: `rtk proxy uv run --frozen pytest -q`
Expected: full suite green except the 6 known-unrelated `tests/test_codex_skills.py` failures from the concurrent paper-annotate workstream's untracked `commands/annotate-paper.md` (pre-existing; not caused by this slice). Zero graph/source-compiler failures.

- [ ] **Step 9: Lint**

Run: `rtk proxy uv run --frozen ruff check science/src/science_tool/graph/materialize.py tests/graph/test_phase_split_contracts.py tests/graph/test_phase_split_emit_derive.py tests/graph/test_phase_split_compile.py`
Expected: no errors.

- [ ] **Step 10: Commit**

```bash
rtk git add science/src/science_tool/graph/materialize.py tests/graph/test_phase_split_compile.py
rtk git commit -m "refactor(source-compiler): unify audit/materialize via _compile pipeline + thin wrappers (Slice C)"
```

---

## Self-Review

**1. Spec coverage:**
- "Split compiler phases" → Task 2 (`_emit_phase`/`_derive_phase` + `EmitResult`) and Task 3 (`_preflight_migration`, `_audit_phase`, `_write_phase`, `_compile`). ✓
- "Unify audit and materialization" → Task 3 `_compile` + thin `materialize_graph`/`materialization_audit`; pinned by `test_single_load_and_audit_call_sites`. ✓
- Public signatures unchanged → Task 3 Step 5 keeps exact signatures; `build_dataset_from_sources` untouched (Task 1 pins it load/audit-free). ✓
- Audit-only path does not raise / preflight / write → `test_audit_only_path_does_not_raise_or_write`, `test_preflight_is_materialize_only`, `test_compile_stop_after_audit_does_not_write`. ✓
- Materialize hard-gate with exact message → `test_materialize_raises_on_audit_failure`; preserved verbatim in `_compile`. ✓
- Same load options on audit path → `_compile` uses `load_project_sources(project_root.resolve(), strict_identity=False)` for both paths. ✓
- `EmitResult` carries `kind_class` + `pre_registration_targets` (dict types) → Task 2 code + `test_emit_phase_returns_build_context`. ✓
- Structural guard scoped to `graph/materialize.py` → `inspect.getsource(m)` on the materialize module only. ✓
- `propagate_freshness_in_memory` untouched → it still calls `_build_dataset_from_sources(sources, source_snapshots=...)`, whose signature is unchanged. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; every command has expected output. ✓

**3. Type consistency:** `EmitResult.pre_registration_targets: dict[URIRef, list[URIRef]]` matches `_pre_registration_commitment_targets` return and `_derive_bears_on_layer`'s parameter. `CompilationResult.audit_rows: list[AuditRow]` matches `audit_project_sources` / `_audit_phase` return. `stop_after: Literal["audit"] | None` used identically in `_compile`, `materialize_graph` (omitted → full), `materialization_audit` (`"audit"`). `_compile` return `CompilationResult` consumed correctly by both wrappers (`.trig_path`, `.audit_rows`, `.has_failures`). ✓
