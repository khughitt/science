# Entity Consolidation P2 — Consolidation-Candidate Detector — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a read-only `science curate consolidation-candidates` detector that reports superseded-lineage clusters (mechanical) and semantic clusters (dep-free heuristics), each with surfaced evidence, taking no action.

**Architecture:** Extract a shared supersedes-graph pass + entity iterator from P1's `consolidation.py` (behaviour-neutral); add a new top-level `consolidation_candidates.py` detector returning a Pydantic report; render it from a new `curate` CLI subcommand. Detector reads canonical `entities/**/*.md` directly — never `collect_inventory`. Semantic clustering is restricted to default-visible entities; lineage is reported unfiltered.

**Tech Stack:** Python 3.12/3.13, Pydantic v2, Click, pytest, PyYAML.

**Spec:** `docs/plans/2026-06-15-entity-consolidation-p2-candidate-detector-design.md` (commit `32fb0266`).

**Test command (run from the worktree's `science/` directory):**
```bash
cd science    # the package root inside the worktree
PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest <test-path> -v
```
> CRITICAL: `PYTHONPATH=src` is mandatory. Without it the shared venv imports the *main* checkout's `science_tool`, silently testing the wrong code. Verify with `PYTHONPATH=src rtk ~/d/science/science/.venv/bin/python -c "import science_tool; print(science_tool.__file__)"` → must print a path under `.worktrees/`.
>
> RTK: per `~/.codex/RTK.md`, shell commands are prefixed with `rtk` (token-optimized proxy). All runnable commands below already carry the `rtk` prefix. If your harness auto-rewrites via the Claude Code hook, run them bare — do not double-prefix.

---

## File Structure

- **Modify** `science/src/science_tool/consolidation.py` — extract `iter_entity_frontmatter` (rename from `_iter_entity_frontmatter`), add `SupersededChain`/`NonLinearComponent`/`SupersedesGraph` dataclasses + `build_supersedes_graph(entries)`; rewire `mark_superseded` to consume them. Behaviour-neutral.
- **Create** `science/src/science_tool/consolidation_candidates.py` — Pydantic report models, the three semantic signals, merge/order, `detect_consolidation_candidates(...)`, and `render_text(...)`.
- **Modify** `science/src/science_tool/curate/cli.py` — add the `consolidation-candidates` subcommand.
- **Create** `science/tests/test_consolidation_graph.py` — direct unit tests for the extracted graph pass.
- **Create** `science/tests/test_consolidation_candidates.py` — detector tests (all §8 cases).
- **Create** `science/tests/test_consolidation_candidates_cli.py` — CLI render + read-only tests.

Existing `science/tests/test_consolidation_mark_superseded.py` (P1) must stay green throughout — it pins the behaviour-neutral refactor.

---

## Task 1: Extract shared supersedes-graph pass (behaviour-neutral refactor)

**Files:**
- Modify: `science/src/science_tool/consolidation.py`
- Test: `science/tests/test_consolidation_graph.py` (Create)
- Regression: `science/tests/test_consolidation_mark_superseded.py` (must stay green)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_consolidation_graph.py`:

```python
"""Unit tests for the shared supersedes-graph pass (P2 refactor of P1)."""

from __future__ import annotations

from pathlib import Path

import yaml


def _write(root: Path, kind_dir: str, name: str, fm: dict) -> None:
    d = root / "entities" / kind_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nbody\n", encoding="utf-8"
    )


def _supersedes(target: str) -> dict:
    return {"predicate": "sci:supersedes", "target": target}


def test_build_supersedes_graph_linear_chain(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: g\n", encoding="utf-8")
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation"})
    _write(tmp_path, "interpretations", "i-v4", {"id": "interpretation:i-v4", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})
    _write(tmp_path, "interpretations", "i-v5", {"id": "interpretation:i-v5", "type": "interpretation", "relations": [_supersedes("interpretation:i-v4")]})

    from science_tool.consolidation import build_supersedes_graph, iter_entity_frontmatter

    graph = build_supersedes_graph(iter_entity_frontmatter(tmp_path))
    assert len(graph.linear) == 1
    chain = graph.linear[0]
    assert chain.survivor == "interpretation:i-v5"
    assert chain.superseded == ("interpretation:i-v3", "interpretation:i-v4")
    assert graph.non_linear == ()
    assert graph.kind_by_id["interpretation:i-v3"] == "interpretation"
    assert graph.status_by_id["interpretation:i-v3"] is None


def test_build_supersedes_graph_non_linear(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: g\n", encoding="utf-8")
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation"})
    _write(tmp_path, "interpretations", "i-a", {"id": "interpretation:i-a", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})
    _write(tmp_path, "interpretations", "i-b", {"id": "interpretation:i-b", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})

    from science_tool.consolidation import build_supersedes_graph, iter_entity_frontmatter

    graph = build_supersedes_graph(iter_entity_frontmatter(tmp_path))
    assert graph.linear == ()
    assert len(graph.non_linear) == 1
    assert graph.non_linear[0].nodes == ("interpretation:i-a", "interpretation:i-b", "interpretation:i-v3")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_graph.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_supersedes_graph'`.

- [ ] **Step 3: Implement the refactor**

In `science/src/science_tool/consolidation.py`, update the imports and add the dataclasses + builder. Replace the top of the file (imports through `_iter_entity_frontmatter`) so the iterator is public:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.entities import _STATUS_VALUES, edit_entity

_SUPERSEDED = "superseded"
_SUPERSEDES_PREDICATE = "sci:supersedes"


def iter_entity_frontmatter(project_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    """All entity markdown frontmatter under entities/, as (path, frontmatter)."""
    entities_root = project_root / "entities"
    out: list[tuple[Path, dict[str, Any]]] = []
    if not entities_root.is_dir():
        return out
    for path in sorted(entities_root.rglob("*.md")):
        fm = read_frontmatter(path)
        if fm and "id" in fm:
            out.append((path, fm))
    return out
```

Keep `_supersedes_targets`, `_kind_of`, `_supports_superseded`, `_connected_components`, `_classify` exactly as they are. After `_classify`, add:

```python
@dataclass(frozen=True)
class SupersededChain:
    """A linear supersedes chain: `survivor` is the in-degree-0 node; `superseded`
    is its sorted tail (every node with in-degree >= 1)."""

    survivor: str
    superseded: tuple[str, ...]


@dataclass(frozen=True)
class NonLinearComponent:
    """A branched/cyclic component — reported, never acted on."""

    nodes: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class SupersedesGraph:
    """Topology of the supersedes graph plus per-id status/kind, derived from one
    pass over the entity frontmatter. Carries NO apply-time filtering — that lives
    in `mark_superseded`."""

    linear: tuple[SupersededChain, ...]
    non_linear: tuple[NonLinearComponent, ...]
    status_by_id: dict[str, str | None]
    kind_by_id: dict[str, str]


def build_supersedes_graph(entries: list[tuple[Path, dict[str, Any]]]) -> SupersedesGraph:
    """Classify supersedes chains from already-iterated `entries`. Edges come from
    canonical `relations:` entries with `predicate: "sci:supersedes"`; edges to
    unknown ids are ignored. Components are split into linear chains (survivor +
    sorted superseded tail) and non-linear components (branched/cyclic)."""
    status_by_id: dict[str, str | None] = {}
    kind_by_id: dict[str, str] = {}
    known: set[str] = set()
    for _path, fm in entries:
        eid = str(fm["id"])
        known.add(eid)
        status_by_id[eid] = fm.get("status")
        kind_by_id[eid] = _kind_of(eid, fm)

    edges: list[tuple[str, str]] = []
    for _path, fm in entries:
        src = str(fm["id"])
        for dst in _supersedes_targets(fm):
            if dst in known:  # ignore edges to unknown ids
                edges.append((src, dst))

    nodes = {n for edge in edges for n in edge}
    linear: list[SupersededChain] = []
    non_linear: list[NonLinearComponent] = []
    for comp in _connected_components(nodes, edges):
        if len(comp) < 2:
            continue
        is_linear, survivor, members = _classify(comp, edges)
        if not is_linear or survivor is None:
            non_linear.append(
                NonLinearComponent(nodes=tuple(sorted(comp)), reason="branched or cyclic supersedes chain")
            )
            continue
        linear.append(SupersededChain(survivor=survivor, superseded=tuple(sorted(members))))
    return SupersedesGraph(
        linear=tuple(linear),
        non_linear=tuple(non_linear),
        status_by_id=status_by_id,
        kind_by_id=kind_by_id,
    )
```

Now rewrite `mark_superseded` (replace the whole function, keeping its docstring) to consume the builder while preserving the exact report shape:

```python
def mark_superseded(project_root: Path, *, apply: bool) -> dict[str, Any]:
    """Scan supersedes chains under ``project_root`` and report (or apply) the
    `superseded` status auto-derivation.

    Returns a dict with keys:
    - ``chains``: linear chains as ``{"survivor", "members" (sorted), "linear": True}``.
    - ``non_linear``: branched/cyclic components as ``{"nodes" (sorted), "reason"}``.
    - ``to_mark``: member ids a linear chain would stamp ``superseded`` (excludes
      already-superseded members and members whose kind can't carry the status).
    - ``applied``: member ids actually stamped (empty unless ``apply=True``).
    - ``skipped_kinds``: ``{"id", "kind"}`` for members whose kind does not declare
      the ``superseded`` status (see ``_supports_superseded``).
    """
    project_root = project_root.resolve()
    graph = build_supersedes_graph(iter_entity_frontmatter(project_root))

    chains: list[dict[str, Any]] = []
    to_mark: list[str] = []
    skipped_kinds: list[dict[str, str]] = []
    for chain in graph.linear:
        chains.append({"survivor": chain.survivor, "members": list(chain.superseded), "linear": True})
        for member in chain.superseded:
            if graph.status_by_id.get(member) == _SUPERSEDED:
                continue  # already superseded
            kind = graph.kind_by_id.get(member, member.split(":", 1)[0])
            if not _supports_superseded(kind):
                skipped_kinds.append({"id": member, "kind": kind})
                continue  # not a built-in 'superseded'-capable kind; can't stamp it
            to_mark.append(member)

    non_linear = [{"nodes": list(comp.nodes), "reason": comp.reason} for comp in graph.non_linear]

    report: dict[str, Any] = {
        "chains": chains,
        "non_linear": non_linear,
        "to_mark": to_mark,
        "applied": [],
        "skipped_kinds": skipped_kinds,
    }
    if apply:
        for member in to_mark:
            edit_entity(project_root, member, status=_SUPERSEDED)
            report["applied"].append(member)
    return report
```

Delete the now-unused `_iter_entity_frontmatter` definition (its body moved verbatim into `iter_entity_frontmatter`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_graph.py tests/test_consolidation_mark_superseded.py -v`
Expected: PASS (2 new + 7 existing P1 tests). The P1 tests passing confirms the refactor is behaviour-neutral.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/consolidation.py science/tests/test_consolidation_graph.py
rtk git commit -m "refactor(consolidation): extract build_supersedes_graph + public iter_entity_frontmatter"
```

---

## Task 2: Detector skeleton + lineage section (unfiltered)

**Files:**
- Create: `science/src/science_tool/consolidation_candidates.py`
- Test: `science/tests/test_consolidation_candidates.py` (Create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_consolidation_candidates.py`:

```python
"""Tests for the read-only consolidation-candidate detector (P2)."""

from __future__ import annotations

from pathlib import Path

import yaml


def _write(root: Path, kind_dir: str, name: str, fm: dict) -> None:
    d = root / "entities" / kind_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nbody\n", encoding="utf-8"
    )


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: cand-test\n", encoding="utf-8")


def _supersedes(target: str) -> dict:
    return {"predicate": "sci:supersedes", "target": target}


def test_lineage_linear_reports_survivor_and_archivable(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation"})
    _write(tmp_path, "interpretations", "i-v4", {"id": "interpretation:i-v4", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})
    _write(tmp_path, "interpretations", "i-v5", {"id": "interpretation:i-v5", "type": "interpretation", "relations": [_supersedes("interpretation:i-v4")]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert len(report.superseded_lineage.linear) == 1
    chain = report.superseded_lineage.linear[0]
    assert chain.survivor == "interpretation:i-v5"
    assert chain.archivable == ["interpretation:i-v3", "interpretation:i-v4"]
    assert chain.members == ["interpretation:i-v3", "interpretation:i-v4", "interpretation:i-v5"]
    assert report.counts["linear"] == 1


def test_lineage_non_linear_reported(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "type": "interpretation"})
    _write(tmp_path, "interpretations", "i-a", {"id": "interpretation:i-a", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})
    _write(tmp_path, "interpretations", "i-b", {"id": "interpretation:i-b", "type": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert report.superseded_lineage.linear == []
    assert len(report.superseded_lineage.non_linear) == 1
    assert report.superseded_lineage.non_linear[0].nodes == ["interpretation:i-a", "interpretation:i-b", "interpretation:i-v3"]


def test_lineage_reports_kind_lacking_superseded_vocab(tmp_path: Path) -> None:
    # workflow-run is supersedes-eligible but declares NO status vocabulary;
    # mark_superseded(apply) skips it, but the read-only detector still reports it.
    _seed(tmp_path)
    _write(tmp_path, "workflow-runs", "wr-old", {"id": "workflow-run:wr-old", "type": "workflow-run"})
    _write(tmp_path, "workflow-runs", "wr-new", {"id": "workflow-run:wr-new", "type": "workflow-run", "relations": [_supersedes("workflow-run:wr-old")]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert len(report.superseded_lineage.linear) == 1
    assert report.superseded_lineage.linear[0].archivable == ["workflow-run:wr-old"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.consolidation_candidates'`.

- [ ] **Step 3: Create the module with models + lineage section**

Create `science/src/science_tool/consolidation_candidates.py`:

```python
"""Read-only consolidation-candidate detector (P2).

Scans canonical ``entities/`` and reports two kinds of consolidation candidates —
superseded-lineage (mechanical) and semantic clusters (dep-free heuristics) —
each with surfaced evidence. Takes NO action. This is the decision-support
surface for the future ``entities consolidate --apply``. See
docs/plans/2026-06-15-entity-consolidation-p2-candidate-detector-design.md.
"""

from __future__ import annotations

import re
from itertools import combinations
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from science_tool.consolidation import (
    SupersedesGraph,
    build_supersedes_graph,
    iter_entity_frontmatter,
)
from science_tool.entities import is_default_visible

_SEQ_PREFIX = re.compile(r"^\d+-")
_VERSION_SUFFIX = re.compile(r"-v\d+$")
_TASK_PREFIX = "task:"


class LinearChain(BaseModel):
    survivor: str
    archivable: list[str]  # the superseded tail (everything but the survivor)
    members: list[str]     # all nodes including the survivor, sorted


class NonLinearChain(BaseModel):
    nodes: list[str]
    reason: str


class SemanticCluster(BaseModel):
    signal: str            # "structural-family" | "shared-anchor" | "related-overlap" (merged: joined with "+")
    members: list[str]
    evidence: str


class SupersededLineage(BaseModel):
    linear: list[LinearChain] = Field(default_factory=list)
    non_linear: list[NonLinearChain] = Field(default_factory=list)


class ConsolidationCandidates(BaseModel):
    project_root: str
    superseded_lineage: SupersededLineage = Field(default_factory=SupersededLineage)
    semantic_clusters: list[SemanticCluster] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


def _lineage_section(graph: SupersedesGraph) -> SupersededLineage:
    linear = [
        LinearChain(
            survivor=chain.survivor,
            archivable=list(chain.superseded),
            members=sorted([chain.survivor, *chain.superseded]),
        )
        for chain in graph.linear
    ]
    non_linear = [NonLinearChain(nodes=list(comp.nodes), reason=comp.reason) for comp in graph.non_linear]
    return SupersededLineage(linear=linear, non_linear=non_linear)


def detect_consolidation_candidates(
    project_root: Path,
    *,
    related_jaccard: float = 0.5,
    min_cluster_size: int = 2,
) -> ConsolidationCandidates:
    """Detect consolidation candidates under ``project_root`` (read-only).

    Lineage is reported unfiltered (regardless of visibility or kind capability);
    semantic clustering considers default-visible entities only.
    """
    project_root = Path(project_root).resolve()
    entries = iter_entity_frontmatter(project_root)
    graph = build_supersedes_graph(entries)
    lineage = _lineage_section(graph)

    semantic: list[SemanticCluster] = []  # populated in Tasks 3-7

    counts = {
        "linear": len(lineage.linear),
        "non_linear": len(lineage.non_linear),
        "semantic": len(semantic),
    }
    return ConsolidationCandidates(
        project_root=str(project_root),
        superseded_lineage=lineage,
        semantic_clusters=semantic,
        counts=counts,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/consolidation_candidates.py science/tests/test_consolidation_candidates.py
rtk git commit -m "feat(consolidation): P2 detector skeleton + unfiltered lineage section"
```

---

## Task 3: Structural-family signal — id-stem (same-kind)

**Files:**
- Modify: `science/src/science_tool/consolidation_candidates.py`
- Test: `science/tests/test_consolidation_candidates.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_consolidation_candidates.py`:

```python
def test_id_stem_clusters_within_a_kind(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "interpretations", "0001-foo-v1", {"id": "interpretation:0001-foo-v1", "type": "interpretation"})
    _write(tmp_path, "interpretations", "0002-foo-v2", {"id": "interpretation:0002-foo-v2", "type": "interpretation"})
    _write(tmp_path, "interpretations", "0003-foo-v3", {"id": "interpretation:0003-foo-v3", "type": "interpretation"})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    family = [c for c in report.semantic_clusters if c.signal == "structural-family"]
    assert len(family) == 1
    assert family[0].members == [
        "interpretation:0001-foo-v1",
        "interpretation:0002-foo-v2",
        "interpretation:0003-foo-v3",
    ]
    assert "id-stem 'foo'" in family[0].evidence


def test_id_stem_does_not_cross_kinds(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "questions", "0001-foo", {"id": "question:0001-foo", "type": "question"})
    _write(tmp_path, "hypotheses", "0002-foo", {"id": "hypothesis:0002-foo", "type": "hypothesis"})
    _write(tmp_path, "interpretations", "0003-foo", {"id": "interpretation:0003-foo", "type": "interpretation"})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert [c for c in report.semantic_clusters if c.signal == "structural-family"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates.py -k id_stem -v`
Expected: FAIL (no `structural-family` clusters produced yet).

- [ ] **Step 3: Implement the id-stem signal**

In `consolidation_candidates.py`, add the helpers and a structural-family builder above `detect_consolidation_candidates`:

```python
def _local_part(entity_id: str) -> str:
    return entity_id.split(":", 1)[1] if ":" in entity_id else entity_id


def _id_stem(entity_id: str) -> str:
    local = _local_part(entity_id)
    local = _SEQ_PREFIX.sub("", local)
    local = _VERSION_SUFFIX.sub("", local)
    return local


def _structural_family_clusters(
    visible: list[tuple[str, str, dict[str, Any]]],
    min_cluster_size: int,
) -> list[SemanticCluster]:
    """Basis-namespaced structural grouping. Keys are (kind, basis, value) so the
    three sub-bases never collide by value; identical member-sets merge later."""
    groups: dict[tuple[str, str, str], list[str]] = {}
    for eid, kind, _fm in visible:
        groups.setdefault((kind, "id-stem", _id_stem(eid)), []).append(eid)

    clusters: list[SemanticCluster] = []
    for (kind, basis, value), members in groups.items():
        if len(members) < min_cluster_size:
            continue
        clusters.append(
            SemanticCluster(
                signal="structural-family",
                members=sorted(members),
                evidence=f"{basis} '{value}' (kind {kind}; {len(members)} members)",
            )
        )
    return clusters
```

Then in `detect_consolidation_candidates`, build the `visible` list and call the builder. Replace the `semantic: list[SemanticCluster] = []  # populated in Tasks 3-7` line with:

```python
    visible: list[tuple[str, str, dict[str, Any]]] = [
        (str(fm["id"]), graph.kind_by_id[str(fm["id"])], fm)
        for _path, fm in entries
        if is_default_visible(graph.status_by_id.get(str(fm["id"])))
    ]
    semantic = _structural_family_clusters(visible, min_cluster_size)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/consolidation_candidates.py science/tests/test_consolidation_candidates.py
rtk git commit -m "feat(consolidation): structural-family id-stem signal (same-kind)"
```

---

## Task 4: Structural-family — group: and task-family sub-bases

**Files:**
- Modify: `science/src/science_tool/consolidation_candidates.py`
- Test: `science/tests/test_consolidation_candidates.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_consolidation_candidates.py`:

```python
def test_group_and_task_family_are_basis_namespaced(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Same value "alpha" reached by DIFFERENT bases must NOT merge into one cluster:
    #   - h1/h2 share group: alpha
    #   - h3/h4 share task:alpha in related
    # id-stems are distinct, so the only structural keys are (group, alpha) and
    # (task-family, task:alpha) -> two separate clusters.
    _write(tmp_path, "hypotheses", "0001-aa", {"id": "hypothesis:0001-aa", "type": "hypothesis", "group": "alpha"})
    _write(tmp_path, "hypotheses", "0002-bb", {"id": "hypothesis:0002-bb", "type": "hypothesis", "group": "alpha"})
    _write(tmp_path, "hypotheses", "0003-cc", {"id": "hypothesis:0003-cc", "type": "hypothesis", "related": ["task:alpha"]})
    _write(tmp_path, "hypotheses", "0004-dd", {"id": "hypothesis:0004-dd", "type": "hypothesis", "related": ["task:alpha"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    family = sorted((c for c in report.semantic_clusters if c.signal == "structural-family"), key=lambda c: c.members)
    assert len(family) == 2
    assert family[0].members == ["hypothesis:0001-aa", "hypothesis:0002-bb"]
    assert "group 'alpha'" in family[0].evidence
    assert family[1].members == ["hypothesis:0003-cc", "hypothesis:0004-dd"]
    assert "task-family 'task:alpha'" in family[1].evidence
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates.py -k basis_namespaced -v`
Expected: FAIL (group/task-family sub-bases not implemented; only id-stem keys exist).

- [ ] **Step 3: Implement the group + task-family sub-bases**

In `consolidation_candidates.py`, add a task-ref helper and extend `_structural_family_clusters`. Add the helper above the builder:

```python
def _task_refs(fm: dict[str, Any]) -> list[str]:
    """`task:`-prefixed refs from `related:` only. PREFIX-SHAPED BY DESIGN (spec
    §6.2): task entities live in `tasks/` (outside the `entities/` scan), so there
    is no loaded task set to resolve against — any `task:`-prefixed string counts.
    Real task-id resolution is a deferred §7 tuning-round concern, not P2."""
    related = fm.get("related")
    items = related if isinstance(related, list) else []
    return sorted({item for item in items if isinstance(item, str) and item.startswith(_TASK_PREFIX)})
```

Then, inside `_structural_family_clusters`, extend the grouping loop body (after the id-stem `setdefault`):

```python
    for eid, kind, _fm in visible:
        groups.setdefault((kind, "id-stem", _id_stem(eid)), []).append(eid)
        group_value = _fm.get("group")
        if isinstance(group_value, str) and group_value:
            groups.setdefault((kind, "group", group_value), []).append(eid)
        for task_ref in _task_refs(_fm):
            groups.setdefault((kind, "task-family", task_ref), []).append(eid)
```

(Replace the existing single-line `for ... setdefault(... "id-stem" ...)` loop with this expanded loop.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/consolidation_candidates.py science/tests/test_consolidation_candidates.py
rtk git commit -m "feat(consolidation): structural-family group: + task-family sub-bases (namespaced)"
```

---

## Task 5: Shared-anchor signal (same-kind, entity-ref hygiene)

**Files:**
- Modify: `science/src/science_tool/consolidation_candidates.py`
- Test: `science/tests/test_consolidation_candidates.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_consolidation_candidates.py`:

```python
def test_shared_anchor_clusters_same_kind(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "hypotheses", "0005-anchor", {"id": "hypothesis:0005-anchor", "type": "hypothesis"})
    for n in ("a", "b", "c"):
        _write(
            tmp_path, "interpretations", f"int-{n}",
            {"id": f"interpretation:int-{n}", "type": "interpretation", "related": ["hypothesis:0005-anchor"]},
        )

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    anchors = [c for c in report.semantic_clusters if c.signal == "shared-anchor"]
    assert len(anchors) == 1
    assert anchors[0].members == ["interpretation:int-a", "interpretation:int-b", "interpretation:int-c"]
    assert "hypothesis:0005-anchor" in anchors[0].evidence


def test_shared_anchor_ignores_unresolved_refs(tmp_path: Path) -> None:
    _seed(tmp_path)
    # The shared ref is a non-entity tag string, not a known kind:slug id -> no cluster.
    for n in ("a", "b", "c"):
        _write(
            tmp_path, "interpretations", f"int-{n}",
            {"id": f"interpretation:int-{n}", "type": "interpretation", "related": ["topic-tag-not-an-entity"]},
        )

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert [c for c in report.semantic_clusters if c.signal == "shared-anchor"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates.py -k shared_anchor -v`
Expected: FAIL (no `shared-anchor` clusters yet).

- [ ] **Step 3: Implement entity-ref hygiene + shared-anchor**

In `consolidation_candidates.py`, add the ref-hygiene helper and the shared-anchor builder above `detect_consolidation_candidates`:

```python
def _entity_refs(fm: dict[str, Any], known_ids: set[str], *, fields: tuple[str, ...]) -> set[str]:
    """Refs from *fields* that resolve to a known entity id (`kind:slug`). Empty,
    tag-like, dict, and non-entity strings are ignored. External `source_refs`
    citations (DOI/PMID/URL/free strings) are absent from `known_ids`, so they are
    excluded automatically."""
    refs: set[str] = set()
    for field in fields:
        value = fm.get(field)
        items = value if isinstance(value, list) else [value] if isinstance(value, str) else []
        for item in items:
            if isinstance(item, str) and item in known_ids:
                refs.add(item)
    return refs


def _shared_anchor_clusters(
    visible: list[tuple[str, str, dict[str, Any]]],
    known_ids: set[str],
    min_cluster_size: int,
) -> list[SemanticCluster]:
    """Same-kind entities whose entity-refs (related + resolvable source_refs) point
    at the same anchor entity."""
    anchor_members: dict[tuple[str, str], set[str]] = {}
    for eid, kind, fm in visible:
        for anchor in _entity_refs(fm, known_ids, fields=("related", "source_refs")):
            if anchor == eid:
                continue  # ignore self-reference
            anchor_members.setdefault((kind, anchor), set()).add(eid)

    clusters: list[SemanticCluster] = []
    for (kind, anchor), members in anchor_members.items():
        if len(members) < min_cluster_size:
            continue
        clusters.append(
            SemanticCluster(
                signal="shared-anchor",
                members=sorted(members),
                evidence=f"{len(members)} {kind} entities all ref {anchor}",
            )
        )
    return clusters
```

Then in `detect_consolidation_candidates`, compute `known_ids` and append shared-anchor clusters. After the `visible = [...]` assignment and the `semantic = _structural_family_clusters(...)` line, change to:

```python
    known_ids = set(graph.kind_by_id)
    semantic = _structural_family_clusters(visible, min_cluster_size)
    semantic += _shared_anchor_clusters(visible, known_ids, min_cluster_size)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/consolidation_candidates.py science/tests/test_consolidation_candidates.py
rtk git commit -m "feat(consolidation): shared-anchor signal + entity-ref hygiene"
```

---

## Task 6: related-overlap signal (Jaccard threshold)

**Files:**
- Modify: `science/src/science_tool/consolidation_candidates.py`
- Test: `science/tests/test_consolidation_candidates.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_consolidation_candidates.py`:

```python
def test_related_overlap_clusters_above_threshold(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Anchors a..d exist as entities so refs resolve.
    for a in ("a", "b", "c", "d"):
        _write(tmp_path, "concepts", f"anchor-{a}", {"id": f"concept:anchor-{a}", "type": "concept"})
    # x={a,b,c}, y={a,b,c,d}: intersection 3, union 4 -> Jaccard 0.75 >= 0.5 : cluster.
    _write(tmp_path, "interpretations", "x", {"id": "interpretation:x", "type": "interpretation",
        "related": ["concept:anchor-a", "concept:anchor-b", "concept:anchor-c"]})
    _write(tmp_path, "interpretations", "y", {"id": "interpretation:y", "type": "interpretation",
        "related": ["concept:anchor-a", "concept:anchor-b", "concept:anchor-c", "concept:anchor-d"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    overlap = [c for c in report.semantic_clusters if c.signal == "related-overlap"]
    assert len(overlap) == 1
    assert overlap[0].members == ["interpretation:x", "interpretation:y"]
    assert "Jaccard" in overlap[0].evidence


def test_related_overlap_below_threshold_no_cluster(tmp_path: Path) -> None:
    _seed(tmp_path)
    for a in ("a", "b", "c"):
        _write(tmp_path, "concepts", f"anchor-{a}", {"id": f"concept:anchor-{a}", "type": "concept"})
    # x={a}, y={a,b,c} -> Jaccard 1/3 = 0.33 < 0.5 : no cluster.
    _write(tmp_path, "interpretations", "x", {"id": "interpretation:x", "type": "interpretation", "related": ["concept:anchor-a"]})
    _write(tmp_path, "interpretations", "y", {"id": "interpretation:y", "type": "interpretation",
        "related": ["concept:anchor-a", "concept:anchor-b", "concept:anchor-c"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert [c for c in report.semantic_clusters if c.signal == "related-overlap"] == []


def test_related_overlap_ignores_non_entity_refs(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Both share only a non-entity tag string -> not counted -> no cluster.
    _write(tmp_path, "interpretations", "x", {"id": "interpretation:x", "type": "interpretation", "related": ["just-a-tag", ""]})
    _write(tmp_path, "interpretations", "y", {"id": "interpretation:y", "type": "interpretation", "related": ["just-a-tag"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    assert [c for c in report.semantic_clusters if c.signal == "related-overlap"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates.py -k related_overlap -v`
Expected: FAIL (no `related-overlap` clusters yet).

- [ ] **Step 3: Implement related-overlap with union-find**

In `consolidation_candidates.py`, add the builder above `detect_consolidation_candidates`:

```python
def _related_overlap_clusters(
    visible: list[tuple[str, str, dict[str, Any]]],
    known_ids: set[str],
    threshold: float,
    min_cluster_size: int,
) -> list[SemanticCluster]:
    """Connected components over entity pairs whose `related:` entity-ref sets have
    Jaccard >= threshold. Kind-agnostic (unlike structural-family / shared-anchor)."""
    related_sets = {
        eid: _entity_refs(fm, known_ids, fields=("related",)) for eid, _kind, fm in visible
    }
    ids = sorted(eid for eid in related_sets if related_sets[eid])

    parent = {eid: eid for eid in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    best_jaccard: dict[str, float] = {eid: 0.0 for eid in ids}
    for a, b in combinations(ids, 2):
        sa, sb = related_sets[a], related_sets[b]
        union_size = len(sa | sb)
        if union_size == 0:
            continue
        jaccard = len(sa & sb) / union_size
        if jaccard >= threshold:
            union(a, b)
            best_jaccard[a] = max(best_jaccard[a], jaccard)
            best_jaccard[b] = max(best_jaccard[b], jaccard)

    components: dict[str, list[str]] = {}
    for eid in ids:
        components.setdefault(find(eid), []).append(eid)

    clusters: list[SemanticCluster] = []
    for members in components.values():
        if len(members) < min_cluster_size:
            continue
        peak = max(best_jaccard[m] for m in members)
        clusters.append(
            SemanticCluster(
                signal="related-overlap",
                members=sorted(members),
                evidence=f"related Jaccard >= {threshold:.2f} (peak {peak:.2f}; {len(members)} members)",
            )
        )
    return clusters
```

Then in `detect_consolidation_candidates`, append related-overlap. Change the semantic assembly block to:

```python
    known_ids = set(graph.kind_by_id)
    semantic = _structural_family_clusters(visible, min_cluster_size)
    semantic += _shared_anchor_clusters(visible, known_ids, min_cluster_size)
    semantic += _related_overlap_clusters(visible, known_ids, related_jaccard, min_cluster_size)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates.py -v`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/consolidation_candidates.py science/tests/test_consolidation_candidates.py
rtk git commit -m "feat(consolidation): related-overlap Jaccard signal"
```

---

## Task 7: Merge identical member-sets, default-visible exclusion, determinism

**Files:**
- Modify: `science/src/science_tool/consolidation_candidates.py`
- Test: `science/tests/test_consolidation_candidates.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_consolidation_candidates.py`:

```python
def test_duplicate_member_sets_merge_evidence(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Same two entities fire BOTH id-stem (shared stem 'foo') AND shared-anchor
    # (both ref hypothesis:0005) -> one merged cluster, both evidences, joined signal.
    # Each carries DISTINCT extra resolvable refs so related-overlap stays below
    # threshold (Jaccard 1/5 = 0.2 < 0.5) and does NOT also fire — keeping the
    # merged signal exactly "shared-anchor+structural-family".
    _write(tmp_path, "hypotheses", "0005-anchor", {"id": "hypothesis:0005-anchor", "type": "hypothesis"})
    for c in ("p", "q", "r", "s"):
        _write(tmp_path, "concepts", f"c-{c}", {"id": f"concept:c-{c}", "type": "concept"})
    _write(tmp_path, "interpretations", "0001-foo-v1",
        {"id": "interpretation:0001-foo-v1", "type": "interpretation",
         "related": ["hypothesis:0005-anchor", "concept:c-p", "concept:c-q"]})
    _write(tmp_path, "interpretations", "0002-foo-v2",
        {"id": "interpretation:0002-foo-v2", "type": "interpretation",
         "related": ["hypothesis:0005-anchor", "concept:c-r", "concept:c-s"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    members = ["interpretation:0001-foo-v1", "interpretation:0002-foo-v2"]
    matching = [c for c in report.semantic_clusters if c.members == members]
    assert len(matching) == 1  # merged, not duplicated
    assert matching[0].signal == "shared-anchor+structural-family"
    assert "id-stem 'foo'" in matching[0].evidence
    assert "hypothesis:0005-anchor" in matching[0].evidence


def test_semantic_excludes_non_default_visible_entities(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Three share stem 'foo', but one is superseded -> excluded from semantic
    # clustering, leaving only 2 visible members. (It still appears in lineage if
    # part of a chain; here it is not.)
    _write(tmp_path, "interpretations", "0001-foo-v1", {"id": "interpretation:0001-foo-v1", "type": "interpretation"})
    _write(tmp_path, "interpretations", "0002-foo-v2", {"id": "interpretation:0002-foo-v2", "type": "interpretation"})
    _write(tmp_path, "interpretations", "0003-foo-v3", {"id": "interpretation:0003-foo-v3", "type": "interpretation", "status": "superseded"})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    report = detect_consolidation_candidates(tmp_path)
    family = [c for c in report.semantic_clusters if c.signal == "structural-family"]
    assert len(family) == 1
    assert family[0].members == ["interpretation:0001-foo-v1", "interpretation:0002-foo-v2"]


def test_report_is_deterministic(tmp_path: Path) -> None:
    _seed(tmp_path)
    _write(tmp_path, "hypotheses", "0005-anchor", {"id": "hypothesis:0005-anchor", "type": "hypothesis"})
    for n in ("a", "b", "c"):
        _write(tmp_path, "interpretations", f"0001-fam-{n}",
            {"id": f"interpretation:0001-fam-{n}", "type": "interpretation", "related": ["hypothesis:0005-anchor"]})

    from science_tool.consolidation_candidates import detect_consolidation_candidates

    first = detect_consolidation_candidates(tmp_path).model_dump(mode="json")
    second = detect_consolidation_candidates(tmp_path).model_dump(mode="json")
    assert first == second
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates.py -k "merge or excludes or deterministic" -v`
Expected: FAIL on `test_duplicate_member_sets_merge_evidence` (un-merged duplicate clusters; signal not joined). The exclusion and determinism tests may already pass from Task 3/7 ordering, but the merge test pins the new behaviour.

- [ ] **Step 3: Implement the merge + ordering**

In `consolidation_candidates.py`, add the merge function above `detect_consolidation_candidates`:

```python
def _merge_and_order(clusters: list[SemanticCluster]) -> list[SemanticCluster]:
    """Merge clusters with identical member-sets into one (signals joined with "+",
    evidences joined with " | " in a deterministic order); sort the result."""
    by_members: dict[tuple[str, ...], list[SemanticCluster]] = {}
    for cluster in clusters:
        by_members.setdefault(tuple(cluster.members), []).append(cluster)

    merged: list[SemanticCluster] = []
    for members, group in by_members.items():
        ordered = sorted(group, key=lambda c: (c.signal, c.evidence))
        signal = "+".join(sorted({c.signal for c in group}))
        evidence = " | ".join(c.evidence for c in ordered)
        merged.append(SemanticCluster(signal=signal, members=list(members), evidence=evidence))

    merged.sort(key=lambda c: (c.signal, c.members))
    return merged
```

Then wrap the semantic assembly in `detect_consolidation_candidates`. Change the assembly block to:

```python
    known_ids = set(graph.kind_by_id)
    raw_clusters = _structural_family_clusters(visible, min_cluster_size)
    raw_clusters += _shared_anchor_clusters(visible, known_ids, min_cluster_size)
    raw_clusters += _related_overlap_clusters(visible, known_ids, related_jaccard, min_cluster_size)
    semantic = _merge_and_order(raw_clusters)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates.py -v`
Expected: PASS (14 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/consolidation_candidates.py science/tests/test_consolidation_candidates.py
rtk git commit -m "feat(consolidation): merge identical member-sets + deterministic ordering"
```

---

## Task 8: CLI subcommand `curate consolidation-candidates` (json/text, read-only)

**Files:**
- Modify: `science/src/science_tool/consolidation_candidates.py` (add `render_text`)
- Modify: `science/src/science_tool/curate/cli.py`
- Test: `science/tests/test_consolidation_candidates_cli.py` (Create)

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_consolidation_candidates_cli.py`:

```python
"""CLI tests for `science curate consolidation-candidates` (read-only)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner


def _write(root: Path, kind_dir: str, name: str, fm: dict) -> None:
    d = root / "entities" / kind_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nbody\n", encoding="utf-8"
    )


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: cli-test\n", encoding="utf-8")


def _fixture(root: Path) -> None:
    _seed(root)
    _write(root, "interpretations", "0001-foo-v1", {"id": "interpretation:0001-foo-v1", "type": "interpretation"})
    _write(root, "interpretations", "0002-foo-v2", {"id": "interpretation:0002-foo-v2", "type": "interpretation"})


def test_cli_json_format(tmp_path: Path) -> None:
    _fixture(tmp_path)
    from science_tool.cli import main

    result = CliRunner().invoke(
        main, ["curate", "consolidation-candidates", "--project-root", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["counts"]["semantic"] == 1
    assert payload["semantic_clusters"][0]["members"] == [
        "interpretation:0001-foo-v1",
        "interpretation:0002-foo-v2",
    ]


def test_cli_text_format(tmp_path: Path) -> None:
    _fixture(tmp_path)
    from science_tool.cli import main

    result = CliRunner().invoke(
        main, ["curate", "consolidation-candidates", "--project-root", str(tmp_path), "--format", "text"]
    )
    assert result.exit_code == 0, result.output
    assert "structural-family" in result.output
    assert "interpretation:0001-foo-v1" in result.output


def test_cli_is_read_only(tmp_path: Path) -> None:
    _fixture(tmp_path)
    from science_tool.cli import main

    paths = sorted((tmp_path / "entities").rglob("*.md"))
    before = {p: p.stat().st_mtime_ns for p in paths}

    result = CliRunner().invoke(
        main, ["curate", "consolidation-candidates", "--project-root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    after = {p: p.stat().st_mtime_ns for p in paths}
    assert before == after  # no file was written
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates_cli.py -v`
Expected: FAIL — `No such command 'consolidation-candidates'`.

- [ ] **Step 3a: Add `render_text` to the detector module**

Append to `science/src/science_tool/consolidation_candidates.py`:

```python
def render_text(report: ConsolidationCandidates) -> str:
    """Deterministic plain-text rendering of a candidates report."""
    lines = [
        f"Consolidation candidates for {report.project_root}",
        f"  superseded lineage: {report.counts['linear']} linear, {report.counts['non_linear']} non-linear",
        f"  semantic clusters:  {report.counts['semantic']}",
    ]
    for chain in report.superseded_lineage.linear:
        lines.append(f"  [linear] survivor {chain.survivor}; archivable {', '.join(chain.archivable)}")
    for comp in report.superseded_lineage.non_linear:
        lines.append(f"  [non-linear] {', '.join(comp.nodes)} — {comp.reason}")
    for cluster in report.semantic_clusters:
        lines.append(f"  [{cluster.signal}] {', '.join(cluster.members)} — {cluster.evidence}")
    return "\n".join(lines)
```

- [ ] **Step 3b: Add the CLI subcommand**

In `science/src/science_tool/curate/cli.py`, append after the existing `inventory_cmd`:

```python
@curate_group.command("consolidation-candidates")
@click.option("--project-root", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path("."), show_default=True)
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json", show_default=True)
@click.option("--related-jaccard", type=float, default=0.5, show_default=True, help="Jaccard threshold for the related-overlap signal.")
@click.option("--min-cluster-size", type=int, default=2, show_default=True, help="Minimum members for a reported cluster.")
def consolidation_candidates_cmd(
    project_root: Path,
    output_format: str,
    related_jaccard: float,
    min_cluster_size: int,
) -> None:
    """Report consolidation candidates (read-only; superseded-lineage + semantic)."""
    from science_tool.consolidation_candidates import detect_consolidation_candidates, render_text

    report = detect_consolidation_candidates(
        project_root, related_jaccard=related_jaccard, min_cluster_size=min_cluster_size
    )
    if output_format == "json":
        click.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        click.echo(render_text(report))
```

`json`, `click`, and `Path` are already imported at the top of `curate/cli.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_candidates_cli.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/consolidation_candidates.py science/src/science_tool/curate/cli.py science/tests/test_consolidation_candidates_cli.py
rtk git commit -m "feat(curate): science curate consolidation-candidates subcommand"
```

---

## Task 9: Full-suite gate

**Files:** none (verification only)

- [ ] **Step 1: Run the consolidation + curate test slice**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest tests/test_consolidation_graph.py tests/test_consolidation_mark_superseded.py tests/test_consolidation_candidates.py tests/test_consolidation_candidates_cli.py tests/test_status_visibility.py -v`
Expected: PASS (all P1 + P2 consolidation/visibility tests).

- [ ] **Step 2: Run the full suite**

Run: `cd science && PYTHONPATH=src rtk ~/d/science/science/.venv/bin/pytest -q`
Expected: PASS, except the two known pre-existing failures unrelated to this work — `test_full_lifecycle` and `test_meta_validate_smoke_runs` (both caused by a missing `science` Rust-shim binary on PATH; verify they also fail on `main` before this branch and are therefore NOT regressions). No other failures.

- [ ] **Step 3: Commit (only if anything changed)**

No code changes expected here. If the full-suite run surfaced an unexpected failure introduced by P2, fix it in the relevant task's file and re-run before proceeding.

---

## Post-implementation (NOT plan code-tasks)

Per the spec §7, after the plan is merged run a **validation + tuning round**: execute `science curate consolidation-candidates --format json` across several recently-active projects (`natural-systems`, `therapeutics`, `meta`, plus others with high entity churn), manually inspect for missed real groups and spurious clusters, then iterate `--related-jaccard` / `--min-cluster-size` and reconsider the deferred signals (title-token overlap, embeddings, external citation anchors). This is exploratory work, not a fixed code task, so it is intentionally excluded from the task list above.

---

## Self-Review

**Spec coverage:**
- Module split (spec §3) → Tasks 1, 2, 8.
- Report model (§4) → Task 2 (models), Tasks 3–7 (semantic), Task 8 (render).
- Lineage unfiltered (§5) → Task 2 (incl. unsupported-kind test).
- Reference hygiene (§6.1) → Task 5 (`_entity_refs`), exercised in 5 & 6.
- structural-family id-stem / group / task-family, basis-namespaced (§6.2) → Tasks 3, 4.
- shared-anchor same-kind (§6.3) → Task 5.
- related-overlap Jaccard (§6.4) → Task 6.
- Merge identical member-sets + ordering (§6.5) → Task 7.
- CLI knobs (§6.6) → Task 8.
- Tests (§8): all listed cases mapped — lineage linear/non-linear/unsupported-kind (T2), id-stem within/cross kind (T3), basis-namespaced (T4), shared-anchor + ignores-unresolved (T5), related-overlap above/below/non-entity (T6), merge + visibility-exclusion + determinism (T7), CLI read-only (T8).
- No `collect_inventory` dependency (§2) → detector imports only from `consolidation` + `entities`; verified in Task 2 imports.

**Placeholder scan:** none — every step has runnable code/commands.

**Type consistency:** `iter_entity_frontmatter`, `build_supersedes_graph`, `SupersedesGraph(.linear/.non_linear/.status_by_id/.kind_by_id)`, `SupersededChain(.survivor/.superseded)`, `NonLinearComponent(.nodes/.reason)`, `detect_consolidation_candidates(project_root, *, related_jaccard, min_cluster_size)`, `ConsolidationCandidates(.superseded_lineage/.semantic_clusters/.counts)`, `LinearChain(.survivor/.archivable/.members)`, `SemanticCluster(.signal/.members/.evidence)`, `_structural_family_clusters`, `_shared_anchor_clusters`, `_related_overlap_clusters`, `_entity_refs`, `_merge_and_order`, `render_text` — names are consistent across all tasks.
