# Source Compiler Slice B — `SourceSnapshot` & Freshness-Origin: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a typed, in-graph-persisted `SourceSnapshot` primitive that pins each loaded
markdown-backed entity file's content hash, diffs it against the prior build, and emits a
typed `sci:SourceChange` freshness-origin that drives the existing `bears_on`/freshness
machinery — content-derived staleness, distinguishable from date-driven staleness.

**Architecture:** Snapshot observation (hash files + read prior `graph.trig`) is filesystem
work done in `materialize_graph` and passed as precomputed data into the otherwise-pure
`_build_dataset_from_sources`. The snapshot layer emits `SourceSnapshot`/`SourceChange`
triples (provenance graph) and `SS sci:bearsOn entity` + reified `BearsOnEdge` (knowledge
graph) before `_derive_bears_on_layer`, so closure and `derive_freshness` propagate snapshot
changes through the existing dependency substrate.

**Tech Stack:** Python 3.13, pydantic, rdflib, pytest. uv workspace (`~/d/science`).

**Design:** `~/d/science/docs/plans/2026-06-15-source-compiler-snapshot-freshness-design.md`

---

## Conventions (all tasks)

- **Worktree.** All work happens in the worktree `~/d/science/.worktrees/source-compiler-snapshot`
  on branch `feat/source-compiler-snapshot`. Every shell step must first
  `cd ~/d/science/.worktrees/source-compiler-snapshot` and verify
  `rtk git branch --show-current` prints `feat/source-compiler-snapshot` before editing or
  committing (commits must not leak to `main`).
- **Tests/lint.** Run from the `science/` member dir:
  `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest <paths>`
  and `… rtk proxy uv run --frozen ruff check <paths>`. (`rtk` has no `uv`/`pytest`
  subcommand; `rtk proxy` passes the raw command through.)
- **Git.** Use `rtk git` for all git. **No `Co-Authored-By` trailers.** Commit at the end of
  each task with the message shown in that task's final step.
- **Paths in docs/comments** use `~/d/`, not machine-specific absolute paths.
- **`science_model` must never import `science_tool`.**
- Source files referenced below are relative to the `science/` member dir unless absolute.

---

## File Structure

- `src/science_tool/graph/source_records.py` — **modify**: add `SourceChange`, `SourceSnapshot`
  (leaf module, stdlib + pydantic only — Slice A's import-cycle guard still holds).
- `src/science_tool/graph/source_snapshots.py` — **create**: URI builders, file hashing,
  `read_prior_snapshots`, `compute_source_snapshots`, `emit_source_snapshots`.
- `src/science_tool/graph/freshness.py` — **modify**: `derive_freshness` gains a required
  `source_changes` keyword.
- `src/science_tool/graph/materialize.py` — **modify**: `_derive_freshness_layer` and
  `_build_dataset_from_sources` thread `source_changes`/`source_snapshots`; `materialize_graph`
  computes snapshots and passes them in.
- Tests under `tests/` and `tests/graph/` as specified per task.

---

## Task 1: Add `SourceSnapshot` + `SourceChange` primitives

**Files:**
- Modify: `src/science_tool/graph/source_records.py`
- Test: `tests/graph/test_source_records_relocation.py` (extend the existing leaf-purity guard)
- Test: `tests/graph/test_source_snapshot_types.py` (create)

- [ ] **Step 1: Write the failing type tests**

Create `tests/graph/test_source_snapshot_types.py`:

```python
"""Shape tests for the SourceSnapshot / SourceChange primitives (Slice B)."""

from __future__ import annotations

from datetime import date

from science_tool.graph.source_records import SourceChange, SourceSnapshot


def test_source_change_is_frozen_and_holds_hash_and_date():
    change = SourceChange(sha256="abc123", observed_on=date(2026, 6, 15))
    assert change.sha256 == "abc123"
    assert change.observed_on == date(2026, 6, 15)
    # frozen dataclass: assignment must raise
    try:
        change.sha256 = "x"  # type: ignore[misc]
    except Exception as exc:  # FrozenInstanceError
        assert "cannot assign" in str(exc).lower() or "frozen" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("SourceChange must be frozen")


def test_source_snapshot_defaults_latest_change_to_none():
    snap = SourceSnapshot(source_path="entities/hypotheses/h1.md", sha256="deadbeef")
    assert snap.source_path == "entities/hypotheses/h1.md"
    assert snap.sha256 == "deadbeef"
    assert snap.latest_change is None


def test_source_snapshot_carries_a_change():
    change = SourceChange(sha256="newhash", observed_on=date(2026, 6, 15))
    snap = SourceSnapshot(source_path="p.md", sha256="newhash", latest_change=change)
    assert snap.latest_change == change
```

- [ ] **Step 2: Run it to confirm failure**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/graph/test_source_snapshot_types.py -q`
Expected: FAIL — `ImportError: cannot import name 'SourceChange'`.

- [ ] **Step 3: Add the primitives**

In `src/science_tool/graph/source_records.py`, add `from datetime import date` to the imports
and append after `AggregateRowMeta`:

```python
@dataclass(frozen=True, slots=True)
class SourceChange:
    """A freshness-origin event: a source's observed content identity changed.

    Emitted only when a current content hash differs from the persisted baseline
    (the first-ever observation establishes the baseline and is NOT a change).
    """

    sha256: str
    observed_on: date


class SourceSnapshot(BaseModel):
    """A pinned observation of a local source's content identity.

    Durable: carried forward verbatim across builds when the content is unchanged
    (`latest_change` and `observed_on` must not drift on an unchanged rebuild).
    `latest_change` stays None until a change is first observed against a baseline.
    """

    source_path: str  # relative, posix
    sha256: str  # sha256 of raw file bytes
    latest_change: SourceChange | None = None
```

- [ ] **Step 4: Extend the leaf-purity guard**

In `tests/graph/test_source_records_relocation.py`, the test that asserts `source_records`
imports nothing from `science_tool` already covers the new types (same module). Add an
explicit import-presence assertion so the guard names them. Append:

```python
def test_new_snapshot_types_are_exported_from_leaf():
    from science_tool.graph import source_records

    assert hasattr(source_records, "SourceSnapshot")
    assert hasattr(source_records, "SourceChange")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/graph/test_source_snapshot_types.py tests/graph/test_source_records_relocation.py -q`
Expected: PASS.

- [ ] **Step 6: Lint + commit**

```bash
cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen ruff check src/science_tool/graph/source_records.py tests/graph/test_source_snapshot_types.py
cd ~/d/science/.worktrees/source-compiler-snapshot && rtk git add science/src/science_tool/graph/source_records.py science/tests/graph/test_source_snapshot_types.py science/tests/graph/test_source_records_relocation.py && rtk git commit -m "feat(source-compiler): add SourceSnapshot + SourceChange primitives (Slice B)"
```

---

## Task 2: Snapshot observation — URIs, hashing, baseline read, diff/carry-forward

**Files:**
- Create: `src/science_tool/graph/source_snapshots.py`
- Test: `tests/graph/test_source_snapshot_compute.py` (create)

- [ ] **Step 1: Write the failing compute tests**

Create `tests/graph/test_source_snapshot_compute.py`:

```python
"""compute_source_snapshots: baseline / change / carry-forward (Slice B)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

from science_tool.graph.source_records import SourceSnapshot
from science_tool.graph.source_snapshots import (
    compute_source_snapshots,
    read_prior_snapshots,
    source_snapshot_uri,
)
from science_tool.graph.store import PROJECT_NS, SCHEMA_NS, SCI_NS


class _Sources:
    """Minimal ProjectSources stand-in for compute (only the read fields)."""

    def __init__(self, project_root: str, entities: list, adapters: dict[str, str]):
        self.project_root = project_root
        self.entities = entities
        self.entity_source_adapters = adapters


class _Entity:
    def __init__(self, canonical_id: str, file_path: str):
        self.canonical_id = canonical_id
        self.file_path = file_path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _prior_graph_with(tmp: Path, *, source_path: str, sha256: str) -> Path:
    """Hand-build a prior graph.trig carrying one baseline snapshot (no change)."""
    ds = Dataset()
    prov = ds.graph(PROJECT_NS["graph/provenance"])
    ss = source_snapshot_uri(source_path)
    prov.add((ss, RDF.type, SCI_NS.SourceSnapshot))
    prov.add((ss, SCI_NS.sourcePath, Literal(source_path)))
    prov.add((ss, SCHEMA_NS.sha256, Literal(sha256)))
    out = tmp / "knowledge" / "graph.trig"
    out.parent.mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(out), format="trig")
    return out


def test_first_build_establishes_baseline_no_change(tmp_path: Path):
    root = tmp_path / "demo"
    _write(root / "entities" / "h1.md", "alpha")
    sources = _Sources(str(root), [_Entity("hypothesis:h1", "entities/h1.md")], {"hypothesis:h1": "markdown"})

    result = compute_source_snapshots(sources, prior_graph_path=root / "knowledge" / "graph.trig", today=date(2026, 6, 15))

    assert len(result.emissions) == 1
    snap = result.emissions[0].snapshot
    assert snap.source_path == "entities/h1.md"
    assert snap.latest_change is None
    assert result.source_changes == {}  # no origin on first observation


def test_unchanged_rebuild_carries_forward_verbatim(tmp_path: Path):
    root = tmp_path / "demo"
    _write(root / "entities" / "h1.md", "alpha")
    import hashlib

    sha = hashlib.sha256(b"alpha").hexdigest()
    prior = _prior_graph_with(root, source_path="entities/h1.md", sha256=sha)
    sources = _Sources(str(root), [_Entity("hypothesis:h1", "entities/h1.md")], {"hypothesis:h1": "markdown"})

    result = compute_source_snapshots(sources, prior_graph_path=prior, today=date(2026, 6, 15))

    snap = result.emissions[0].snapshot
    assert snap.sha256 == sha
    assert snap.latest_change is None  # unchanged → no event, no churn
    assert result.source_changes == {}


def test_changed_content_mints_one_source_change(tmp_path: Path):
    root = tmp_path / "demo"
    _write(root / "entities" / "h1.md", "BETA")  # differs from baseline below
    prior = _prior_graph_with(root, source_path="entities/h1.md", sha256="oldhash")
    sources = _Sources(str(root), [_Entity("hypothesis:h1", "entities/h1.md")], {"hypothesis:h1": "markdown"})

    result = compute_source_snapshots(sources, prior_graph_path=prior, today=date(2026, 6, 15))

    snap = result.emissions[0].snapshot
    assert snap.latest_change is not None
    assert snap.latest_change.observed_on == date(2026, 6, 15)
    assert snap.sha256 == snap.latest_change.sha256
    assert result.source_changes == {str(source_snapshot_uri("entities/h1.md")): date(2026, 6, 15)}


def test_only_markdown_backed_entities_are_snapshotted(tmp_path: Path):
    root = tmp_path / "demo"
    _write(root / "entities" / "h1.md", "alpha")
    sources = _Sources(
        str(root),
        [_Entity("hypothesis:h1", "entities/h1.md"), _Entity("dataset:d1", "data/d1.csv")],
        {"hypothesis:h1": "markdown", "dataset:d1": "datapackage"},
    )

    result = compute_source_snapshots(sources, prior_graph_path=root / "knowledge" / "graph.trig", today=date(2026, 6, 15))

    assert [e.entity_canonical_id for e in result.emissions] == ["hypothesis:h1"]


def test_missing_prior_graph_is_empty_baseline(tmp_path: Path):
    assert read_prior_snapshots(tmp_path / "nope" / "graph.trig") == {}


def test_empty_prior_graph_is_empty_baseline(tmp_path: Path):
    p = tmp_path / "graph.trig"
    p.write_text("")  # first build writes an empty graph.trig
    assert read_prior_snapshots(p) == {}


def test_corrupt_prior_graph_fails_loud(tmp_path: Path):
    import pytest

    bad = tmp_path / "graph.trig"
    bad.write_text("@@ this is not valid trig @@ <<<>>>")
    with pytest.raises(Exception):  # corrupt non-empty must NOT be silently empty-baselined
        read_prior_snapshots(bad)
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/graph/test_source_snapshot_compute.py -q`
Expected: FAIL — `ModuleNotFoundError: science_tool.graph.source_snapshots`.

- [ ] **Step 3: Create the module**

Create `src/science_tool/graph/source_snapshots.py`:

```python
"""Source-observation layer (patchwork kernel Spec 3, Slice B).

Observes the content identity of each loaded markdown-backed entity file, diffs it
against the prior build's persisted SourceSnapshots, and emits typed SourceChange
freshness-origins. Filesystem-touching (file hashing + prior-graph read); called by
`materialize_graph`, which passes the precomputed result into the pure
`_build_dataset_from_sources`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

from science_tool.graph.freshness import _emit_bears_on_edge
from science_tool.graph.io import _sha256_file, entity_uri_for_ref
from science_tool.graph.source_records import SourceChange, SourceSnapshot
from science_tool.graph.store import PROJECT_NS, SCHEMA_NS, SCI_NS

MARKDOWN_ADAPTER_NAME = "markdown"


def source_snapshot_uri(source_path: str) -> URIRef:
    """Stable per-path snapshot-node IRI (sha256-slugged for IRI safety)."""
    digest = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:16]
    return URIRef(PROJECT_NS[f"source-snapshot/{digest}"])


def source_change_uri(source_path: str, sha256: str) -> URIRef:
    """Stable per-(path, new-hash) change-event IRI → carry-forward is byte-identical."""
    key = f"{source_path}\x00{sha256}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return URIRef(PROJECT_NS[f"source-change/{digest}"])


@dataclass(frozen=True)
class _PriorSnapshot:
    sha256: str
    latest_change: SourceChange | None


@dataclass(frozen=True)
class SourceSnapshotEmission:
    """One snapshot ready to emit, plus the entity it backs (bears_on target)."""

    snapshot: SourceSnapshot
    entity_canonical_id: str


@dataclass(frozen=True)
class SourceSnapshotResult:
    emissions: list[SourceSnapshotEmission] = field(default_factory=list)
    # snapshot-node URI str -> observed_on of the current latest change (freshness input)
    source_changes: dict[str, date] = field(default_factory=dict)


def read_prior_snapshots(prior_graph_path: Path) -> dict[str, _PriorSnapshot]:
    """Read baseline snapshots from a prior graph.trig.

    Missing file, or an empty / whitespace-only / pre-Slice-B graph (parses to no
    SourceSnapshot nodes) → empty baseline. A corrupt NON-EMPTY graph.trig is NOT
    swallowed: it raises, because silently treating it as empty would suppress the
    very source-change event Slice B exists to detect.
    """
    if not prior_graph_path.exists():
        return {}
    text = prior_graph_path.read_text(encoding="utf-8")
    if not text.strip():
        return {}  # empty / whitespace-only = valid empty baseline
    dataset = Dataset()
    dataset.parse(data=text, format="trig")  # corrupt non-empty → raises (fail loud)
    prov = dataset.graph(PROJECT_NS["graph/provenance"])
    prior: dict[str, _PriorSnapshot] = {}
    for ss in prov.subjects(RDF.type, SCI_NS.SourceSnapshot):
        path_lit = prov.value(ss, SCI_NS.sourcePath)
        sha_lit = prov.value(ss, SCHEMA_NS.sha256)
        if path_lit is None or sha_lit is None:
            continue
        change_node = prov.value(ss, SCI_NS.latestSourceChange)
        latest: SourceChange | None = None
        if change_node is not None:
            c_sha = prov.value(change_node, SCHEMA_NS.sha256)
            c_on = prov.value(change_node, SCI_NS.observedOn)
            if c_sha is not None and c_on is not None:
                latest = SourceChange(sha256=str(c_sha), observed_on=date.fromisoformat(str(c_on)))
        prior[str(path_lit)] = _PriorSnapshot(sha256=str(sha_lit), latest_change=latest)
    return prior


def compute_source_snapshots(sources: Any, *, prior_graph_path: Path, today: date) -> SourceSnapshotResult:
    """Observe + diff + carry-forward snapshots for loaded markdown-backed entities."""
    prior = read_prior_snapshots(prior_graph_path)
    project_root = Path(sources.project_root)
    result = SourceSnapshotResult()
    for entity in sources.entities:
        if sources.entity_source_adapters.get(entity.canonical_id) != MARKDOWN_ADAPTER_NAME:
            continue
        rel_path = entity.file_path
        abs_path = project_root / rel_path
        current_hash = _sha256_file(abs_path)  # fail loud if unreadable/missing
        prior_snap = prior.get(rel_path)
        if prior_snap is None:
            snap = SourceSnapshot(source_path=rel_path, sha256=current_hash, latest_change=None)
        elif prior_snap.sha256 == current_hash:
            snap = SourceSnapshot(source_path=rel_path, sha256=current_hash, latest_change=prior_snap.latest_change)
        else:
            change = SourceChange(sha256=current_hash, observed_on=today)
            snap = SourceSnapshot(source_path=rel_path, sha256=current_hash, latest_change=change)
        result.emissions.append(SourceSnapshotEmission(snapshot=snap, entity_canonical_id=entity.canonical_id))
        if snap.latest_change is not None:
            result.source_changes[str(source_snapshot_uri(rel_path))] = snap.latest_change.observed_on
    return result


def emit_source_snapshots(dataset: Dataset, result: SourceSnapshotResult) -> None:
    """Emit snapshot/change triples (provenance) + SS bears_on entity (knowledge)."""
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for emission in result.emissions:
        snap = emission.snapshot
        ss = source_snapshot_uri(snap.source_path)
        provenance.add((ss, RDF.type, SCI_NS.SourceSnapshot))
        provenance.add((ss, SCI_NS.sourcePath, Literal(snap.source_path)))
        provenance.add((ss, SCHEMA_NS.sha256, Literal(snap.sha256)))

        entity_uri = entity_uri_for_ref(emission.entity_canonical_id)
        knowledge.add((ss, SCI_NS.bearsOn, entity_uri))
        _emit_bears_on_edge(knowledge, ss, entity_uri, 1)

        change = snap.latest_change
        if change is not None:
            change_node = source_change_uri(snap.source_path, change.sha256)
            provenance.add((ss, SCI_NS.latestSourceChange, change_node))
            provenance.add((change_node, RDF.type, SCI_NS.SourceChange))
            provenance.add((change_node, SCHEMA_NS.sha256, Literal(change.sha256)))
            provenance.add((change_node, SCI_NS.observedOn, Literal(change.observed_on.isoformat(), datatype=XSD.date)))
```

> Note: `compute_source_snapshots` is typed `sources: Any` to avoid importing
> `ProjectSources` from `sources.py` (which imports the adapter modules); it reads only
> `project_root`, `entities`, `entity_source_adapters`. `_emit_bears_on_edge` and
> `_sha256_file`/`entity_uri_for_ref` are reused so snapshot edges and hashes follow the
> exact existing contracts. `freshness.py` and `io.py` do not import this module → no cycle.

- [ ] **Step 4: Run compute tests to verify they pass**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/graph/test_source_snapshot_compute.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Lint + commit**

```bash
cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen ruff check src/science_tool/graph/source_snapshots.py tests/graph/test_source_snapshot_compute.py
cd ~/d/science/.worktrees/source-compiler-snapshot && rtk git add science/src/science_tool/graph/source_snapshots.py science/tests/graph/test_source_snapshot_compute.py && rtk git commit -m "feat(source-compiler): observe + diff source snapshots with carry-forward (Slice B)"
```

---

## Task 3: Emit snapshot triples + reified `bears_on` edge

**Files:**
- (No source change — `emit_source_snapshots` was written in Task 2.)
- Test: `tests/graph/test_source_snapshot_emit.py` (create)

- [ ] **Step 1: Write the failing emit tests**

Create `tests/graph/test_source_snapshot_emit.py`:

```python
"""emit_source_snapshots: graph contract + reified bears_on edge (Slice B)."""

from __future__ import annotations

from datetime import date

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

from science_tool.graph.io import entity_uri_for_ref
from science_tool.graph.source_records import SourceChange, SourceSnapshot
from science_tool.graph.source_snapshots import (
    SourceSnapshotEmission,
    SourceSnapshotResult,
    emit_source_snapshots,
    source_change_uri,
    source_snapshot_uri,
)
from science_tool.graph.store import PROJECT_NS, SCHEMA_NS, SCI_NS


def _emit(result: SourceSnapshotResult) -> Dataset:
    ds = Dataset()
    emit_source_snapshots(ds, result)
    return ds


def test_unchanged_snapshot_emits_node_and_bears_on_but_no_change(tmp_path):
    snap = SourceSnapshot(source_path="entities/h1.md", sha256="h", latest_change=None)
    result = SourceSnapshotResult(emissions=[SourceSnapshotEmission(snap, "hypothesis:h1")])
    ds = _emit(result)

    prov = ds.graph(PROJECT_NS["graph/provenance"])
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    ss = source_snapshot_uri("entities/h1.md")
    entity = entity_uri_for_ref("hypothesis:h1")

    assert (ss, RDF.type, SCI_NS.SourceSnapshot) in prov
    assert (ss, SCI_NS.sourcePath, Literal("entities/h1.md")) in prov
    assert (ss, SCHEMA_NS.sha256, Literal("h")) in prov
    assert (ss, SCI_NS.bearsOn, entity) in knowledge
    # no SourceChange when latest_change is None
    assert prov.value(ss, SCI_NS.latestSourceChange) is None
    assert list(prov.subjects(RDF.type, SCI_NS.SourceChange)) == []


def test_snapshot_bears_on_emits_reified_depth1_edge():
    snap = SourceSnapshot(source_path="entities/h1.md", sha256="h", latest_change=None)
    result = SourceSnapshotResult(emissions=[SourceSnapshotEmission(snap, "hypothesis:h1")])
    ds = _emit(result)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    ss = source_snapshot_uri("entities/h1.md")
    entity = entity_uri_for_ref("hypothesis:h1")

    edge_nodes = [
        n
        for n in knowledge.subjects(RDF.type, SCI_NS.BearsOnEdge)
        if (n, SCI_NS.bearsOnSource, ss) in knowledge and (n, SCI_NS.bearsOnTarget, entity) in knowledge
    ]
    assert len(edge_nodes) == 1
    assert (edge_nodes[0], SCI_NS.bearsOnDepth, Literal(1, datatype=XSD.integer)) in knowledge


def test_changed_snapshot_emits_linked_source_change():
    change = SourceChange(sha256="newh", observed_on=date(2026, 6, 15))
    snap = SourceSnapshot(source_path="entities/h1.md", sha256="newh", latest_change=change)
    result = SourceSnapshotResult(emissions=[SourceSnapshotEmission(snap, "hypothesis:h1")])
    ds = _emit(result)
    prov = ds.graph(PROJECT_NS["graph/provenance"])
    ss = source_snapshot_uri("entities/h1.md")
    change_node = source_change_uri("entities/h1.md", "newh")

    assert (ss, SCI_NS.latestSourceChange, change_node) in prov
    assert (change_node, RDF.type, SCI_NS.SourceChange) in prov
    assert (change_node, SCHEMA_NS.sha256, Literal("newh")) in prov
    assert (change_node, SCI_NS.observedOn, Literal("2026-06-15", datatype=XSD.date)) in prov
```

- [ ] **Step 2: Run to verify pass (emit already implemented in Task 2)**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/graph/test_source_snapshot_emit.py -q`
Expected: PASS (3 tests). If any fail, fix `emit_source_snapshots` in
`src/science_tool/graph/source_snapshots.py` to match the contract above.

- [ ] **Step 3: Commit**

```bash
cd ~/d/science/.worktrees/source-compiler-snapshot && rtk git add science/tests/graph/test_source_snapshot_emit.py && rtk git commit -m "test(source-compiler): pin snapshot graph contract + reified bears_on edge (Slice B)"
```

---

## Task 4: Extend `derive_freshness` with `source_changes`; thread through the builder

**Files:**
- Modify: `src/science_tool/graph/freshness.py`
- Modify: `src/science_tool/graph/materialize.py` (`_derive_freshness_layer`,
  `_build_dataset_from_sources`)
- Modify: `tests/test_freshness_derivation.py` (existing direct callers pass `source_changes={}`)
- Test: `tests/test_freshness_source_origin.py` (create)

- [ ] **Step 1: Write the failing source-origin freshness tests**

Create `tests/test_freshness_source_origin.py`:

```python
"""derive_freshness: content-derived staleness via SourceSnapshot origins (Slice B)."""

from __future__ import annotations

from datetime import date

from rdflib import Dataset, URIRef

from science_model.entities import EntityClass
from science_tool.graph.freshness import EntityFreshnessInfo, derive_freshness
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _u(local: str) -> URIRef:
    return URIRef(PROJECT_NS[local])


def _ds(pairs: list[tuple[URIRef, URIRef]]) -> Dataset:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for s, o in pairs:
        knowledge.add((s, SCI_NS.bearsOn, o))
    return ds


def _entity_info() -> dict[str, EntityFreshnessInfo]:
    return {
        str(_u("hypothesis/h1")): {
            "kind_class": EntityClass.EPISTEMIC,
            "last_reviewed": date(2026, 5, 1),
            "created": date(2026, 4, 1),
            "updated": date(2026, 4, 1),
            "review_horizon_days": None,
        }
    }


def _state(ds: Dataset, target: URIRef) -> str | None:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for _, _, o in knowledge.triples((target, SCI_NS.freshnessState, None)):
        return str(o)
    return None


def _triggered(ds: Dataset, target: URIRef) -> set[str]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {str(o) for _, _, o in knowledge.triples((target, SCI_NS.triggeredBy, None))}


def test_snapshot_change_after_baseline_marks_needs_review():
    ss = _u("source-snapshot/abc")
    ds = _ds([(ss, _u("hypothesis/h1"))])
    derive_freshness(
        ds,
        entities=_entity_info(),
        today=date(2026, 6, 15),
        source_changes={str(ss): date(2026, 6, 10)},  # after last_reviewed 2026-05-01
    )
    assert _state(ds, _u("hypothesis/h1")) == "needs-review"
    assert _triggered(ds, _u("hypothesis/h1")) == {str(ss)}  # triggeredBy -> snapshot node


def test_snapshot_change_before_baseline_does_not_trigger():
    ss = _u("source-snapshot/abc")
    ds = _ds([(ss, _u("hypothesis/h1"))])
    derive_freshness(
        ds,
        entities=_entity_info(),
        today=date(2026, 6, 15),
        source_changes={str(ss): date(2026, 4, 15)},  # before last_reviewed 2026-05-01
    )
    assert _state(ds, _u("hypothesis/h1")) == "fresh"
    assert _triggered(ds, _u("hypothesis/h1")) == set()


def test_empty_source_changes_preserves_date_driven_behavior():
    ds = _ds([(_u("dataset/d1"), _u("hypothesis/h1"))])
    info = _entity_info()
    info[str(_u("dataset/d1"))] = {
        "kind_class": EntityClass.OPERATIONAL,
        "last_reviewed": None,
        "created": date(2026, 4, 1),
        "updated": date(2026, 4, 1),
        "review_horizon_days": None,
    }
    derive_freshness(ds, entities=info, today=date(2026, 6, 15), source_changes={})
    assert _state(ds, _u("hypothesis/h1")) == "fresh"
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/test_freshness_source_origin.py -q`
Expected: FAIL — `derive_freshness() got an unexpected keyword argument 'source_changes'`.

- [ ] **Step 3: Extend `derive_freshness`**

In `src/science_tool/graph/freshness.py`, change the signature and the upstream loop. New
signature:

```python
def derive_freshness(
    dataset: Dataset,
    *,
    entities: dict[str, EntityFreshnessInfo],
    today: date,
    source_changes: dict[str, date],
) -> None:
```

Add to the docstring (after the existing algorithm note): a line documenting
`source_changes` — "maps a SourceSnapshot node URI (str) to the observed_on of its current
SourceChange. An upstream snapshot node uses that date as its change_at, so a content change
triggers needs-review even when authored `updated:` did not move. triggeredBy points to the
snapshot node (typed sci:SourceSnapshot in the graph), keeping the cause distinguishable
from date-driven entity triggers."

Replace the per-source loop body (currently starting `source_info = entities.get(...)`):

```python
        for source_uri in bears_on_in.get(entity_uri, set()):
            source_key = str(source_uri)
            if source_key in source_changes:
                change_at: date | None = source_changes[source_key]
            else:
                source_info = entities.get(source_key)
                if source_info is None:
                    continue
                change_at = source_info.get("updated") or source_info.get("created")
                if change_at is None:
                    continue
            if change_at > baseline:
                triggered.append(source_uri)
                if upstream_change_at is None or change_at > upstream_change_at:
                    upstream_change_at = change_at
```

- [ ] **Step 4: Thread `source_changes` through materialize callers**

In `src/science_tool/graph/materialize.py`:

`_derive_freshness_layer` — add the parameter and forward it:

```python
def _derive_freshness_layer(
    dataset: Dataset,
    *,
    entities: dict[str, EntityFreshnessInfo],
    today: _date,
    source_changes: dict[str, _date],
) -> None:
    """Derive freshness state triples (sci:freshnessState / sci:upstreamChangeAt / sci:triggeredBy).

    Gated on sources.freshness_enabled — skipped entirely when opt-out is active.
    `source_changes` maps SourceSnapshot node URIs to their latest SourceChange observed_on
    (the values are `datetime.date`; `date` is imported as `_date` in this file).
    """
    derive_freshness(dataset, entities=entities, today=today, source_changes=source_changes)
```

`_build_dataset_from_sources` — add the `source_snapshots` parameter, emit the snapshot layer
before bears_on, and pass `source_changes` to freshness. Change the signature:

```python
def _build_dataset_from_sources(
    sources: ProjectSources, *, source_snapshots: "SourceSnapshotResult | None" = None
) -> Dataset:
```

Add the import near the other graph-layer imports at the top of the file:

```python
from science_tool.graph.source_snapshots import SourceSnapshotResult, emit_source_snapshots
```

Insert the emission immediately after `_validate_no_amendment_cycles(dataset)` and before
`_derive_bears_on_layer(`:

```python
    if source_snapshots is not None:
        emit_source_snapshots(dataset, source_snapshots)
```

Replace the freshness block:

```python
    if sources.freshness_enabled:
        entity_meta = _build_entity_meta(sources, kind_class)
        source_changes = source_snapshots.source_changes if source_snapshots is not None else {}
        _derive_freshness_layer(
            dataset, entities=entity_meta, today=_date.today(), source_changes=source_changes
        )
```

- [ ] **Step 5: Update existing direct `derive_freshness` callers**

In `tests/test_freshness_derivation.py`, every direct `derive_freshness(ds, entities=...,
today=...)` call must pass `source_changes={}`. Add `source_changes={}` to each call (these
are date-driven scenarios with no snapshot origins, so `{}` is the correct, explicit value).

> Find them with:
> `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/test_freshness_derivation.py -q`
> — failures will name each `TypeError` call site. There are no production direct callers
> besides `_derive_freshness_layer` (updated in Step 4).

- [ ] **Step 6: Run the affected suites**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/test_freshness_source_origin.py tests/test_freshness_derivation.py tests/test_graph_freshness_integration.py tests/test_freshness_opt_out.py -q`
Expected: PASS. (Integration/opt-out still pass because `materialize_graph` does not yet pass
`source_snapshots`, so `source_changes` defaults to `{}` — behavior unchanged.)

- [ ] **Step 7: Lint + commit**

```bash
cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen ruff check src/science_tool/graph/freshness.py src/science_tool/graph/materialize.py tests/test_freshness_source_origin.py
cd ~/d/science/.worktrees/source-compiler-snapshot && rtk git add science/src/science_tool/graph/freshness.py science/src/science_tool/graph/materialize.py science/tests/test_freshness_source_origin.py science/tests/test_freshness_derivation.py && rtk git commit -m "feat(source-compiler): derive_freshness consumes SourceSnapshot origins (Slice B)"
```

---

## Task 5: Wire snapshots into `materialize_graph`; end-to-end + idempotency

**Files:**
- Modify: `src/science_tool/graph/materialize.py` (`materialize_graph`)
- Test: `tests/test_source_snapshot_freshness_e2e.py` (create)

- [ ] **Step 1: Write the failing end-to-end tests**

Create `tests/test_source_snapshot_freshness_e2e.py`:

```python
"""E2E: content change without an `updated:` bump drives freshness via snapshots (Slice B)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.source_snapshots import source_snapshot_uri
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"))


def _build_min_project(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    _write(root / "science.yaml", "name: demo\nknowledge_profiles:\n  local: core\n")
    _write(root / "knowledge" / "graph.trig", "")
    _write(
        root / "entities" / "hypotheses" / "h1.md",
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
    return root


def _load(path: Path) -> Dataset:
    ds = Dataset()
    ds.parse(source=str(path), format="trig")
    return ds


def _state(ds: Dataset, target: URIRef) -> str | None:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for _, _, o in knowledge.triples((target, SCI_NS.freshnessState, None)):
        return str(o)
    return None


def _entity_uri(canonical_id: str) -> URIRef:
    from science_tool.graph.io import entity_uri_for_ref

    return entity_uri_for_ref(canonical_id)


def test_first_build_establishes_baseline_no_change_node(tmp_path: Path):
    root = _build_min_project(tmp_path)
    trig = materialize_graph(root, strict=False)
    ds = _load(trig)
    prov = ds.graph(PROJECT_NS["graph/provenance"])

    ss = source_snapshot_uri("entities/hypotheses/h1.md")
    assert (ss, RDF.type, SCI_NS.SourceSnapshot) in prov
    # baseline: no SourceChange, entity not stale-by-source
    assert prov.value(ss, SCI_NS.latestSourceChange) is None
    h1 = _entity_uri("hypothesis:h1")
    # an entity with last_reviewed after created and no upstream change is fresh
    assert _state(ds, h1) == "fresh"


def test_content_edit_without_updated_bump_marks_needs_review(tmp_path: Path):
    root = _build_min_project(tmp_path)
    materialize_graph(root, strict=False)  # build 1: baseline

    # Edit the BODY only; leave the `updated:` frontmatter untouched.
    h1_path = root / "entities" / "hypotheses" / "h1.md"
    h1_path.write_text(h1_path.read_text().replace("Original body.", "Edited body — new evidence."))

    trig = materialize_graph(root, strict=False)  # build 2: detects content change
    ds = _load(trig)
    h1 = _entity_uri("hypothesis:h1")

    assert _state(ds, h1) == "needs-review"
    # triggeredBy points to the snapshot node (typed SourceSnapshot), not an entity
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    prov = ds.graph(PROJECT_NS["graph/provenance"])
    triggers = {str(o) for _, _, o in knowledge.triples((h1, SCI_NS.triggeredBy, None))}
    ss = source_snapshot_uri("entities/hypotheses/h1.md")
    assert str(ss) in triggers
    assert (ss, RDF.type, SCI_NS.SourceSnapshot) in prov
    # the change cause is reachable: snapshot -> latestSourceChange -> observedOn/sha256
    change_node = prov.value(ss, SCI_NS.latestSourceChange)
    assert change_node is not None
    assert prov.value(change_node, SCI_NS.observedOn) is not None


def test_unchanged_rebuild_is_snapshot_idempotent(tmp_path: Path):
    root = _build_min_project(tmp_path)
    trig = materialize_graph(root, strict=False)
    snap_triples_1 = _snapshot_triples(_load(trig))

    trig = materialize_graph(root, strict=False)  # rebuild, no edits
    snap_triples_2 = _snapshot_triples(_load(trig))

    assert snap_triples_1 == snap_triples_2  # no churn, no drift


def _snapshot_triples(ds: Dataset) -> set[tuple[str, str, str]]:
    """All SourceSnapshot/SourceChange-related provenance triples, as comparable strings."""
    prov = ds.graph(PROJECT_NS["graph/provenance"])
    out: set[tuple[str, str, str]] = set()
    for ss in prov.subjects(RDF.type, SCI_NS.SourceSnapshot):
        for p, o in prov.predicate_objects(ss):
            out.add((str(ss), str(p), str(o)))
    for c in prov.subjects(RDF.type, SCI_NS.SourceChange):
        for p, o in prov.predicate_objects(c):
            out.add((str(c), str(p), str(o)))
    return out
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/test_source_snapshot_freshness_e2e.py -q`
Expected: FAIL — `test_first_build…` finds no `SourceSnapshot` node (materialize_graph does
not yet compute snapshots).

- [ ] **Step 3: Wire `materialize_graph`**

In `src/science_tool/graph/materialize.py`, add the import near the other snapshot import:

```python
from science_tool.graph.source_snapshots import compute_source_snapshots
```

In `materialize_graph`, replace the build line. Current:

```python
    dataset = _build_dataset_from_sources(sources)

    trig_path = project_root / DEFAULT_GRAPH_PATH
```

New (compute snapshots from the prior graph + disk, then build):

```python
    trig_path = project_root / DEFAULT_GRAPH_PATH
    # Snapshot OBSERVATION is compiler/provenance state and runs UNCONDITIONALLY — it is not
    # gated on freshness_enabled. Gating it would stop persisting SourceSnapshot provenance
    # when freshness is off and lose baseline continuity, so re-enabling freshness later would
    # miss every intervening content change. Only the freshness-STATE derivation (inside
    # `_build_dataset_from_sources`, the `if sources.freshness_enabled` block) is gated.
    snapshots = compute_source_snapshots(sources, prior_graph_path=trig_path, today=_date.today())
    dataset = _build_dataset_from_sources(sources, source_snapshots=snapshots)
```

(`trig_path` is computed before the build so it can be read as the prior-graph baseline; the
existing `trig_path.parent.mkdir(...)` + `save_graph_dataset(dataset, trig_path)` lines stay.)

- [ ] **Step 4: Run the e2e suite to verify pass**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/test_source_snapshot_freshness_e2e.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Characterization — existing freshness unchanged on a no-content-change build**

Append to `tests/test_source_snapshot_freshness_e2e.py`:

```python
def test_snapshot_layer_does_not_perturb_entity_freshness_when_unchanged(tmp_path: Path):
    """The additive snapshot nodes must not change entity freshnessState when no content changed."""
    from science_tool.graph.materialize import _build_dataset_from_sources
    from science_tool.graph.sources import load_project_sources
    from science_tool.graph.source_snapshots import compute_source_snapshots
    from datetime import date as _d

    root = _build_min_project(tmp_path)
    sources = load_project_sources(root, strict_identity=False)

    # Baseline build WITHOUT the snapshot layer (pre-Slice-B behavior).
    ds_without = _build_dataset_from_sources(sources)
    # Build WITH a freshly-computed (first-observation, no-change) snapshot layer.
    snaps = compute_source_snapshots(sources, prior_graph_path=root / "knowledge" / "graph.trig", today=_d(2026, 6, 15))
    ds_with = _build_dataset_from_sources(sources, source_snapshots=snaps)

    def _freshness(ds):
        k = ds.graph(PROJECT_NS["graph/knowledge"])
        return {(str(s), str(o)) for s, _, o in k.triples((None, SCI_NS.freshnessState, None))}

    assert _freshness(ds_without) == _freshness(ds_with)  # no change → identical entity freshness


def test_snapshot_provenance_persists_when_freshness_disabled(tmp_path: Path):
    """Snapshot OBSERVATION is not gated on freshness_enabled (High-2): baseline persists,
    but no freshness-state triples are emitted."""
    root = _build_min_project(tmp_path)
    # Disable freshness-state emission. Mirror the `freshness:` opt-out YAML shape used by
    # tests/test_freshness_opt_out.py (the canonical opt-out fixture).
    (root / "science.yaml").write_text(
        "name: demo\nknowledge_profiles:\n  local: core\nfreshness:\n  enabled: false\n"
    )
    trig = materialize_graph(root, strict=False)
    ds = _load(trig)
    prov = ds.graph(PROJECT_NS["graph/provenance"])
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    ss = source_snapshot_uri("entities/hypotheses/h1.md")

    assert (ss, RDF.type, SCI_NS.SourceSnapshot) in prov  # baseline persists regardless
    assert list(knowledge.triples((None, SCI_NS.freshnessState, None))) == []  # state gated off
```

> Confirm the opt-out YAML key against `tests/test_freshness_opt_out.py` before running; use
> that file's exact `freshness:` shape if it differs from the snippet above.

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/test_source_snapshot_freshness_e2e.py -q`
Expected: PASS (5 tests).

- [ ] **Step 6: Full suite — confirm no regressions**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest -q`
Expected: all green (no new failures vs the pre-Slice-B baseline; new tests pass). The printed
summary line may be swallowed by warning capture — confirm via exit code 0, or add
`--junit-xml=/tmp/sliceb.xml` and read `testsuite tests/failures/errors`.

- [ ] **Step 7: Lint + commit**

```bash
cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen ruff check src/science_tool/graph/materialize.py tests/test_source_snapshot_freshness_e2e.py
cd ~/d/science/.worktrees/source-compiler-snapshot && rtk git add science/src/science_tool/graph/materialize.py science/tests/test_source_snapshot_freshness_e2e.py && rtk git commit -m "feat(source-compiler): wire SourceSnapshot freshness origins into materialize_graph (Slice B)"
```

---

## Task 6: Make `graph propagate-freshness` (in-memory sweep) snapshot-aware

`propagate_freshness_in_memory` builds its dataset via `_build_dataset_from_sources` but passes
no snapshots, so the read-only `graph propagate-freshness` sweep stays blind to content-derived
staleness — the exact failure mode Slice B fixes, left open on a second surface. Compute
snapshots from the prior materialized graph + disk and pass them in. The sweep discards the
dataset (nothing is persisted); it reports "what would be stale if rebuilt now."

**Files:**
- Modify: `src/science_tool/graph/freshness.py` (`propagate_freshness_in_memory`)
- Test: `tests/test_source_snapshot_freshness_e2e.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_source_snapshot_freshness_e2e.py`:

```python
def test_in_memory_sweep_sees_content_change(tmp_path: Path):
    from science_tool.graph.freshness import propagate_freshness_in_memory

    root = _build_min_project(tmp_path)
    materialize_graph(root, strict=False)  # baseline persisted to graph.trig

    h1_path = root / "entities" / "hypotheses" / "h1.md"
    h1_path.write_text(h1_path.read_text().replace("Original body.", "Edited body."))

    rows = propagate_freshness_in_memory(root)
    states = {row["id"]: row["state"] for row in rows}
    assert states.get("hypothesis:h1") == "needs-review"  # content-derived, no `updated:` bump
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/test_source_snapshot_freshness_e2e.py::test_in_memory_sweep_sees_content_change -q`
Expected: FAIL — the sweep is snapshot-blind, so `hypothesis:h1` is absent from the non-fresh
rows (`states.get(...)` is None).

- [ ] **Step 3: Wire snapshots into the sweep**

In `src/science_tool/graph/freshness.py`, in `propagate_freshness_in_memory`, replace:

```python
    if not sources.freshness_enabled:
        return []

    dataset = _build_dataset_from_sources(sources)
```

with:

```python
    if not sources.freshness_enabled:
        return []

    # Lazy imports avoid the freshness -> source_snapshots -> freshness import cycle
    # (source_snapshots imports _emit_bears_on_edge from this module).
    from science_tool.graph.source_snapshots import compute_source_snapshots
    from science_tool.graph.store import DEFAULT_GRAPH_PATH

    prior_graph_path = project_root.resolve() / DEFAULT_GRAPH_PATH
    snapshots = compute_source_snapshots(sources, prior_graph_path=prior_graph_path, today=date.today())
    dataset = _build_dataset_from_sources(sources, source_snapshots=snapshots)
```

(`date` is already imported at the top of `freshness.py`; `DEFAULT_GRAPH_PATH` is exported from
`science_tool.graph.store`.)

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest tests/test_source_snapshot_freshness_e2e.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Lint + commit**

```bash
cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen ruff check src/science_tool/graph/freshness.py tests/test_source_snapshot_freshness_e2e.py
cd ~/d/science/.worktrees/source-compiler-snapshot && rtk git add science/src/science_tool/graph/freshness.py science/tests/test_source_snapshot_freshness_e2e.py && rtk git commit -m "feat(source-compiler): in-memory freshness sweep consumes SourceSnapshot origins (Slice B)"
```

- [ ] **Step 6: Full suite after the in-memory sweep change**

Run: `cd ~/d/science/.worktrees/source-compiler-snapshot/science && rtk proxy uv run --frozen pytest -q`
Expected: all green. This is the final full-suite gate for Slice B; Task 6 changes production
freshness behavior after Task 5's full-suite run, so do not rely on the earlier gate alone.

---

## Final review (after all tasks)

- [ ] Dispatch a final holistic code review over the whole branch diff (`rtk git diff main...HEAD`)
  against the design doc: snapshot scope = loaded markdown-backed entities only; `triggeredBy`
  homogeneous (→ snapshot node); current/latest cause only (no history); idempotent/no-churn;
  `science_model` untouched; no import cycle; full suite green.
- [ ] Then use **superpowers:finishing-a-development-branch** to complete (merge to local `main`,
  `--no-ff`, NOT pushed — Dropbox-synced local-only repo).

## Self-review notes (plan author)

- **Spec coverage:** §5 primitives → Task 1; §6/§7 observe+diff+emit → Tasks 2–3; §8
  derive_freshness → Task 4; §7 materialize wiring + §9 idempotency + §11.5/§11.6 e2e &
  characterization → Task 5; in-memory freshness sweep coverage → Task 6. §10 error handling
  (fail-loud on unreadable file) is inherent in `_sha256_file`; the empty-baseline cases are
  tested in Tasks 2 & 5.
- **Type consistency:** `SourceSnapshotResult.source_changes` values are `date`; the freshness
  param is `dict[str, date]`; the materialize layer annotation note (Task 4 Step 4) flags the
  cosmetic `str` vs `_date` choice. `source_snapshot_uri`/`source_change_uri`/`entity_uri_for_ref`
  signatures are used identically across Tasks 2, 3, 5, and 6.
- **No placeholders:** every code/test step contains the full content to write.
