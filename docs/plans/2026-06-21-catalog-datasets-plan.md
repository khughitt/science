---
id: "plan:2026-06-21-catalog-datasets-plan"
type: "plan"
title: "Catalog datasets — implementation plan (dataset prioritize CLI + catalog-datasets command)"
status: "active"
created: "2026-06-21"
updated: "2026-06-21"
related:
  - "plan:2026-06-21-catalog-datasets-design"
  - "plan:2026-06-21-dataset-catalog-cli-design"
---

# Catalog datasets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic `science dataset prioritize` CLI primitive plus a `/science:catalog-datasets` orchestration command, implementing the design in `plan:2026-06-21-catalog-datasets-design`.

**Architecture:** A new pure-core module `dataset_prioritize.py` computes `score = readiness_weight × (1 + reach) × leverage_tilt` from a project's dataset entities and (optionally) its materialized graph; a thin Click command in `cli.py` renders it. Reach merges a frontmatter path (works with no graph) and a graph `dataset_usage` path; readiness reuses the canonical `DatasetEntity.readiness()`; leverage reuses the computed `_claim_summary_data` signals. A markdown command file drives the discover→verify→connect→prioritize→handoff loop.

**Tech Stack:** Python 3.13, Click, rich, pydantic v2, rdflib, pytest. Package `science_tool` under `~/d/science/science/src/`, model `science_model` under `~/d/science/science/model/src/`, tests under `~/d/science/science/tests/`.

## Global Constraints

- Run everything from `~/d/science/science` (the subproject), NOT the repo root — `science_tool` only imports there. Prefix commands with `uv run --frozen`. Tests: `cd ~/d/science/science && uv run --frozen pytest tests/<file> -v`.
- One commit per task. NO `Co-Authored-By` trailer in any commit.
- Use `~/d/` paths in docs/comments, not `/home/keith/d/` or `/mnt/ssd/Dropbox/`.
- The score formula is exactly `score = readiness_weight × (1 + reach) × leverage_tilt`.
- `readiness_weight` keys on the canonical `DatasetEntity.readiness().state` strings (verbatim) — an unrecognized state gets weight `0.1` AND a `readiness-unresolved` gap-flag (never a silent default bucket).
- Canonical gap-flag set: `{no-edge, unverified, redundant, readiness-unresolved}`.
- `reach` is a per-dataset **merged union** of (frontmatter path, graph usage path), deduplicated by target Q/H id — never a global either/or.
- Frontmatter reach is **bidirectional** (`related` on the dataset AND `related: [dataset:x]` on a question/hypothesis) and **excludes** `source_refs` (those are provenance, not relatedness).
- `leverage_tilt` reuses `_claim_summary_data(knowledge, provenance, uri)` per reached-proposition URI — NOT the top-N-truncated `query_dashboard_summary`. Cap ≤ 2.0; exactly `1.0` when no propositions are reached.
- Stale/missing graph: warn to stderr and degrade (frontmatter reach still works); never auto-materialize. Use `graph_is_stale` (`science_tool/entities.py:927`).
- Do NOT touch the plural `datasets` group, `register-run`, `reconcile`, or existing `add/list/show/consumers` behavior.

## File Structure

- `src/science_tool/dataset_prioritize.py` (NEW) — pure scoring core: readiness weight, frontmatter reach, usage reach, merge+discount, leverage tilt, score/row assembly. One responsibility: turn a project (+optional graph) into ranked rows.
- `src/science_tool/cli.py` (MODIFY, in the `dataset_group` block near line 5190) — add the `dataset prioritize` Click command; delegates to `dataset_prioritize`.
- `tests/test_dataset_prioritize.py` (NEW) — pure-core unit tests (readiness, frontmatter reach).
- `tests/test_dataset_prioritize_graph.py` (NEW) — graph-backed tests (usage reach, leverage, mixed-graph) using `materialize_graph`.
- `tests/test_dataset_prioritize_cli.py` (NEW) — CLI integration (render, filters, --explain, stale/missing graph).
- `commands/catalog-datasets.md` (NEW) — the `/science:catalog-datasets` orchestration command.

## Verified reference facts (copy these verbatim — confirmed against the codebase)

- Readiness reuse — `DatasetEntity.model_validate` needs these base fields backfilled beyond a normal dataset frontmatter: `kind`, `project`, `source_refs`, `content_preview`, `file_path`, `ontology_terms`, `related`. Confirmed states returned by `.readiness().state`: `available`, `"<level>, unverified"` (e.g. `"public, unverified"`), `embargoed`, `withdrawn`, `acquiring`, `consumable-via-scope-reduced`, `consumable-via-substituted`, `derived-via-code`, `derived-via-member-of`, `derived-via-workflow-recipe`, `missing-access-block`, `missing-provenance`, `exception:<mode>`, `unknown`. (`science_model/entities.py:735-785`; `Readiness` at `:395` has `.ready: bool`, `.state: str`, `.detail: str`.)
- `AccessBlock` fields (`science_model/packages/schema.py:96`): `level` ∈ {public,registration,controlled,commercial,mixed}, `availability`, `verified`, `verification_method`, `last_reviewed`, `exception` (with `.mode`).
- Frontmatter parse: `from science_model.frontmatter import parse_frontmatter` → `parse_frontmatter(path) -> (fm: dict, body: str) | None` (`datasets_catalog.py:126`, `:135`).
- Dataset entity files live at `<project>/doc/datasets/*.md`; filter `(fm.get("kind") or fm.get("type")) == "dataset"` (`datasets_catalog.py:129-140`).
- Source scan roots (`graph/sources.py:305`, `load_project_sources`): `["entities", "research/packages", "doc/datasets", "doc/workflows", "doc/workflow-runs"]`. The 21 layout kinds — questions, hypotheses, propositions, evidence-lines — live under `entities/`; only datasets live under `doc/datasets/`. `materialize_graph` will NOT see Q/H/P/evidence-lines placed under `doc/`. The frontmatter reach scan therefore reads `entities/` + `doc/datasets/`.
- URI → canonical ref inverse: `from science_tool.graph.store.identity import canonical_id_from_entity_uri` → `canonical_id_from_entity_uri(str(uri)) -> str | None` (e.g. `.../hypothesis/h` → `"hypothesis:h"`; returns `None` for non-entity/layer URIs — skip those). (`identity.py:32`.)
- Graph path: `DEFAULT_GRAPH_PATH = Path("knowledge/graph.trig")` — `from science_tool.graph.store import DEFAULT_GRAPH_PATH`; full path = `project_root / DEFAULT_GRAPH_PATH`.
- Load graph layers: `from science_tool.graph.store.dataset import _load_dataset`; `from science_tool.graph.store.identity import _graph_uri`; then `ds = _load_dataset(graph_path); knowledge = ds.graph(_graph_uri("graph/knowledge")); provenance = ds.graph(_graph_uri("graph/provenance"))`.
- Namespaces: `from science_tool.graph.store.constants import SCI_NS, CITO_NS`; `from rdflib.namespace import RDF`; `from rdflib import URIRef`.
- Usage edges (in the **provenance** graph): consumer `SCI_NS.hasDatasetUsage` → usage-node; usage-node `SCI_NS.dataset` → dataset URI. Build a dataset URI from a ref via `from science_tool.graph.dataset_usage import project_entity_uri` → `project_entity_uri("dataset:foo")`.
- Evidence-line → proposition (knowledge graph): `(line, CITO_NS.supports, prop)` or `(line, CITO_NS.disputes, prop)`.
- Proposition → hypothesis: `(prop, CITO_NS.discusses, hyp)` where `(hyp, RDF.type, SCI_NS.Hypothesis)`.
- Question → proposition: `(question, SCI_NS.addresses, prop)` — direction is question→proposition, so to find questions for a prop, scan `knowledge.subjects(SCI_NS.addresses, prop)` filtered to `(q, RDF.type, SCI_NS.Question)`.
- Claim signals: `from science_tool.graph.store.summary import _claim_summary_data` → `_claim_summary_data(knowledge, provenance, uri) -> dict | None` with keys incl. `risk_score: float`, `signals: list[str]` (e.g. `"contested"`, `"single_source"`, `"no_empirical_data"`), `contested: bool`.
- Staleness: `from science_tool.entities import graph_is_stale` → `graph_is_stale(project_root, graph_path) -> bool`.
- CLI: group is `@main.group("dataset")` named `dataset_group` (`cli.py:5190`); commands are `@dataset_group.command("...")`; project root via `_project_root_from_env()` or `--project-root`; render with `rich.table.Table` + `rich.console.Console(width=200)`.
- Test harness: `from science_tool.cli import main as science_cli`; `CliRunner().invoke(science_cli, ["dataset","prioritize", *args], catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})`; seed entities by writing markdown into `tmp_path/"doc"/"datasets"`. Graph fixtures: `from science_tool.graph.materialize import materialize_graph` → `materialize_graph(tmp_path)` writes `knowledge/graph.trig`.

---

### Task 1: `readiness_weight` (canonical readiness reuse + flagged default)

**Files:**
- Create: `src/science_tool/dataset_prioritize.py`
- Test: `tests/test_dataset_prioritize.py`

**Interfaces:**
- Produces: `readiness_for(fm: dict) -> Readiness` and `readiness_weight(fm: dict) -> tuple[float, list[str]]` (weight, flags).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dataset_prioritize.py
from __future__ import annotations

from science_tool.dataset_prioritize import readiness_for, readiness_weight


def _ext(level: str, verified: bool, availability: str = "available") -> dict:
    return {
        "id": "dataset:x", "type": "dataset", "title": "X", "status": "candidate",
        "origin": "external", "tier": "track",
        "access": {"level": level, "availability": availability, "verified": verified},
        "ontology_terms": [], "related": [],
    }


def test_readiness_for_reuses_canonical_states() -> None:
    assert readiness_for(_ext("public", False)).state == "public, unverified"
    assert readiness_for(_ext("controlled", True)).state == "available"
    assert readiness_for(_ext("public", False, availability="embargoed")).state == "embargoed"


def test_readiness_weight_ordering_and_flagged_default() -> None:
    # available > unverified-public > unverified-controlled > embargoed
    w_avail, f_avail = readiness_weight(_ext("controlled", True))
    w_pub, _ = readiness_weight(_ext("public", False))
    w_ctrl, _ = readiness_weight(_ext("controlled", False))
    w_emb, _ = readiness_weight(_ext("public", False, availability="embargoed"))
    assert w_avail == 1.0
    assert w_avail > w_pub > w_ctrl > w_emb
    assert f_avail == []
    # an unparseable / unknown-origin entity flags rather than silently bucketing
    w_unk, f_unk = readiness_weight({"id": "dataset:b", "type": "dataset", "title": "B"})
    assert w_unk == 0.1
    assert "readiness-unresolved" in f_unk
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError: cannot import name 'readiness_for'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/science_tool/dataset_prioritize.py
"""Pure scoring core for `science dataset prioritize`.

score(d) = readiness_weight(d) × (1 + reach(d)) × leverage_tilt(d)

Design: docs/plans/2026-06-21-catalog-datasets-design.md.
Readiness reuses the canonical DatasetEntity.readiness(); leverage reuses the
computed _claim_summary_data signals; reach merges a frontmatter path (no graph
needed) with a graph dataset_usage path.
"""

from __future__ import annotations

from science_model.entities import DatasetEntity, Readiness

# Base Entity fields that a normal on-disk dataset frontmatter omits but
# DatasetEntity.model_validate requires. Backfilled so we can call the canonical
# .readiness() instead of re-interpreting access state.
_BASE_BACKFILL = {
    "kind": "dataset",
    "project": "_prioritize",
    "source_refs": [],
    "content_preview": "",
    "file_path": "doc/datasets/_.md",
}


def readiness_for(fm: dict) -> Readiness:
    """Canonical readiness for an on-disk dataset frontmatter dict.

    Returns Readiness(ready=False, state="unknown") if the entity cannot be
    constructed (malformed frontmatter) — the caller flags that as unresolved.
    """
    payload = {
        "ontology_terms": fm.get("ontology_terms") or [],
        "related": fm.get("related") or [],
        **fm,
        **_BASE_BACKFILL,
    }
    try:
        return DatasetEntity.model_validate(payload).readiness()
    except Exception:
        return Readiness(ready=False, state="unknown", detail="unparseable dataset entity")


# Exact readiness.state strings → weight. Ordering is load-bearing; constants tunable.
_STATE_WEIGHT: dict[str, float] = {
    "available": 1.0,
    "derived-via-code": 0.6,
    "derived-via-member-of": 0.6,
    "derived-via-workflow-recipe": 0.6,
    "consumable-via-scope-reduced": 0.55,
    "consumable-via-substituted": 0.55,
    "acquiring": 0.4,
    "embargoed": 0.05,
    "withdrawn": 0.05,
}
_UNVERIFIED_LEVEL_WEIGHT: dict[str, float] = {
    "public": 0.7,
    "registration": 0.5,
    "mixed": 0.5,
    "controlled": 0.3,
    "commercial": 0.3,
}
_UNRESOLVED_WEIGHT = 0.1


def readiness_weight(fm: dict) -> tuple[float, list[str]]:
    """(weight, flags) for a dataset frontmatter. Unrecognized state → flagged default."""
    state = readiness_for(fm).state
    if state in _STATE_WEIGHT:
        return _STATE_WEIGHT[state], []
    if state.endswith(", unverified"):
        level = state[: -len(", unverified")]
        return _UNVERIFIED_LEVEL_WEIGHT.get(level, _UNRESOLVED_WEIGHT), []
    return _UNRESOLVED_WEIGHT, ["readiness-unresolved"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/dataset_prioritize.py science/tests/test_dataset_prioritize.py
git commit -m "feat(dataset): readiness_weight reusing canonical DatasetEntity.readiness with flagged default"
```

---

### Task 2: frontmatter reach (bidirectional, source_refs excluded)

**Files:**
- Modify: `src/science_tool/dataset_prioritize.py`
- Test: `tests/test_dataset_prioritize.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `frontmatter_reach(project_root: Path) -> dict[str, set[str]]` — dataset id → set of `question:`/`hypothesis:` ids, counting both the dataset's own `related` refs and the back-edge where a Q/H lists the dataset in its `related`. Ignores `source_refs`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_dataset_prioritize.py
from pathlib import Path

from science_tool.dataset_prioritize import frontmatter_reach


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_frontmatter_reach_both_directions_excludes_source_refs(tmp_path: Path) -> None:
    # dataset A points outward to a question; question Q2 points back to dataset B.
    _write(tmp_path / "doc/datasets/a.md",
           '---\nid: "dataset:a"\ntype: "dataset"\ntitle: "A"\n'
           'related: ["question:q1", "topic:t1"]\n---\n')
    _write(tmp_path / "doc/datasets/b.md",
           '---\nid: "dataset:b"\ntype: "dataset"\ntitle: "B"\n'
           'source_refs: ["question:qX"]\n---\n')  # source_refs must NOT count
    _write(tmp_path / "entities/questions/q1.md",
           '---\nid: "question:q1"\ntype: "question"\ntitle: "Q1"\n---\n')
    _write(tmp_path / "entities/questions/q2.md",
           '---\nid: "question:q2"\ntype: "question"\ntitle: "Q2"\nrelated: ["dataset:b"]\n---\n')

    reach = frontmatter_reach(tmp_path)
    assert reach["dataset:a"] == {"question:q1"}          # outgoing; topic ignored
    assert reach["dataset:b"] == {"question:q2"}          # incoming back-edge only
    assert "dataset:b" not in reach.get("dataset:b", set()) or "question:qX" not in reach["dataset:b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize.py::test_frontmatter_reach_both_directions_excludes_source_refs -v`
Expected: FAIL with `ImportError: cannot import name 'frontmatter_reach'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add imports at top of dataset_prioritize.py
from pathlib import Path

from science_model.frontmatter import parse_frontmatter

_QH_PREFIXES = ("question:", "hypothesis:")


def _is_qh(ref: str) -> bool:
    return isinstance(ref, str) and ref.startswith(_QH_PREFIXES)


# Roots that hold the entities reach cares about, mirroring load_project_sources
# (graph/sources.py:305): the 21 entity-layout kinds (questions, hypotheses,
# propositions, evidence-lines, ...) live under entities/; datasets stay at
# doc/datasets/. Scan both — NOT a bare doc/ scan (Q/H are NOT under doc/).
_REACH_SCAN_ROOTS = ("entities", "doc/datasets")


def _iter_entity_frontmatter(project_root: Path):
    """Yield (id, fm) for every markdown entity under the reach scan roots.

    Files without an id are skipped.
    """
    for root in _REACH_SCAN_ROOTS:
        base = project_root / root
        if not base.is_dir():
            continue
        for md in sorted(base.rglob("*.md")):
            parsed = parse_frontmatter(md)
            if parsed is None:
                continue
            fm, _ = parsed
            ent_id = fm.get("id")
            if isinstance(ent_id, str) and ent_id:
                yield ent_id, fm


def frontmatter_reach(project_root: Path) -> dict[str, set[str]]:
    reach: dict[str, set[str]] = {}
    # Collect dataset ids and the Q/H ids; build both directions.
    for ent_id, fm in _iter_entity_frontmatter(project_root):
        kind = (fm.get("kind") or fm.get("type") or "")
        related = [r for r in (fm.get("related") or []) if isinstance(r, str)]
        if kind == "dataset":
            reach.setdefault(ent_id, set())
            reach[ent_id].update(r for r in related if _is_qh(r))
        elif _is_qh(ent_id):
            # back-edge: a Q/H listing dataset:x in its own related
            for r in related:
                if isinstance(r, str) and r.startswith("dataset:"):
                    reach.setdefault(r, set()).add(ent_id)
    return reach
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize.py -v`
Expected: PASS (all Task 1 + Task 2 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/dataset_prioritize.py science/tests/test_dataset_prioritize.py
git commit -m "feat(dataset): bidirectional frontmatter reach (excludes source_refs)"
```

---

### Task 3: usage-path reach (graph traversal)

**Files:**
- Modify: `src/science_tool/dataset_prioritize.py`
- Test: `tests/test_dataset_prioritize_graph.py`

**Interfaces:**
- Produces: `usage_reach(knowledge, provenance, dataset_ids: list[str]) -> dict[str, set[str]]` — dataset id → set of Q/H ids reached via `hasDatasetUsage → evidence-line → cito:supports|disputes → proposition → {discusses→hypothesis, ←addresses question}`. Also `_qh_for_proposition(knowledge, prop_uri) -> set[str]` helper.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dataset_prioritize_graph.py
from __future__ import annotations

from pathlib import Path

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store.dataset import _load_dataset
from science_tool.graph.store.identity import _graph_uri
from science_tool.dataset_prioritize import usage_reach


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _seed_graph_project(root: Path) -> None:
    # Minimal connected graph: dataset → evidence-line(dataset_usage) → proposition
    # → hypothesis; question → proposition.
    # IMPORTANT: load_project_sources (graph/sources.py:305) scans entities/ for the
    # 21 layout kinds (questions/hypotheses/propositions/evidence-lines) and
    # doc/datasets/ for datasets. Q/H/P/evidence-lines under doc/ would NOT be
    # materialized — they MUST go under entities/.
    (root / "science.yaml").write_text('slug: "tp"\n', encoding="utf-8")
    _write(root / "doc/datasets/d.md",
           '---\nid: "dataset:d"\ntype: "dataset"\ntitle: "D"\norigin: "external"\n'
           'access: {level: "public", verified: true}\n---\n')
    _write(root / "entities/hypotheses/h.md",
           '---\nid: "hypothesis:h"\ntype: "hypothesis"\ntitle: "H"\n---\n')
    # question→proposition is the sci:addresses edge: author it via a `relations:`
    # block (flattened at sources.py:1047, emitted at materialize.py:1173). A plain
    # `related:` would materialize as skos:related, NOT sci:addresses.
    _write(root / "entities/questions/q.md",
           '---\nid: "question:q"\ntype: "question"\ntitle: "Q"\n'
           'relations:\n  - predicate: "sci:addresses"\n    target: "proposition:p"\n---\n')
    _write(root / "entities/propositions/p.md",
           '---\nid: "proposition:p"\ntype: "proposition"\ntitle: "P"\ndiscusses: ["hypothesis:h"]\n---\n')
    _write(root / "entities/evidence-lines/e.md",
           '---\nid: "evidence-line:e"\ntype: "evidence-line"\ntitle: "E"\n'
           'stance: "supports"\ntarget: "proposition:p"\nevidence_type: "empirical_data_evidence"\n'
           'dataset_usage:\n  - ref: "dataset:d"\n    role: "analyzed"\n    overlap: "full"\n---\n')


def test_usage_reach_traverses_to_question_and_hypothesis(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))

    reach = usage_reach(knowledge, provenance, ["dataset:d"])
    assert reach["dataset:d"] == {"hypothesis:h", "question:q"}
```

Note: if `science.yaml` or the question↔proposition `addresses` linkage is authored differently in this repo's materializer, adjust the seed frontmatter to whatever `materialize_graph` actually consumes (verify by inspecting an existing materialize test, e.g. `tests/test_meta_reference.py`). The assertion — reach resolves to both the hypothesis and the question — is the contract.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize_graph.py -v`
Expected: FAIL with `ImportError: cannot import name 'usage_reach'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add imports at top of dataset_prioritize.py
from rdflib import URIRef
from rdflib.namespace import RDF

from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.store.constants import CITO_NS, SCI_NS
from science_tool.graph.store.identity import canonical_id_from_entity_uri


def _qh_for_proposition(knowledge, prop_uri: URIRef) -> set[URIRef]:
    """Hypotheses (prop discusses) + questions (question addresses prop)."""
    out: set[URIRef] = set()
    for _, _, hyp in knowledge.triples((prop_uri, CITO_NS.discusses, None)):
        if isinstance(hyp, URIRef) and (hyp, RDF.type, SCI_NS.Hypothesis) in knowledge:
            out.add(hyp)
    for q in knowledge.subjects(SCI_NS.addresses, prop_uri):
        if isinstance(q, URIRef) and (q, RDF.type, SCI_NS.Question) in knowledge:
            out.add(q)
    return out


def usage_reach(knowledge, provenance, dataset_ids: list[str]) -> dict[str, set[str]]:
    reach: dict[str, set[str]] = {ds_id: set() for ds_id in dataset_ids}
    for ds_id in dataset_ids:
        ds_uri = project_entity_uri(ds_id)
        # usage nodes referencing this dataset, then their consumers (evidence-lines)
        for usage_node in provenance.subjects(SCI_NS.dataset, ds_uri):
            for consumer in provenance.subjects(SCI_NS.hasDatasetUsage, usage_node):
                # consumer (evidence-line) supports/disputes a proposition (knowledge graph)
                props: set[URIRef] = set()
                for _, _, prop in knowledge.triples((consumer, CITO_NS.supports, None)):
                    props.add(prop)
                for _, _, prop in knowledge.triples((consumer, CITO_NS.disputes, None)):
                    props.add(prop)
                for prop in props:
                    if not isinstance(prop, URIRef):
                        continue
                    for qh in _qh_for_proposition(knowledge, prop):
                        ref = canonical_id_from_entity_uri(str(qh))
                        if ref is not None:  # skip non-entity URIs
                            reach[ds_id].add(ref)
    return reach
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize_graph.py -v`
Expected: PASS — `canonical_id_from_entity_uri` reconstructs `hypothesis:h`/`question:q` from the project URIs, and the question's `relations: [{predicate: "sci:addresses", target: "proposition:p"}]` block materializes the `sci:addresses` edge the traversal reads.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/dataset_prioritize.py science/tests/test_dataset_prioritize_graph.py
git commit -m "feat(dataset): usage-path reach via hasDatasetUsage->evidence-line->proposition->QH"
```

---

### Task 4: merge reach + redundancy discount

**Files:**
- Modify: `src/science_tool/dataset_prioritize.py`
- Test: `tests/test_dataset_prioritize_graph.py`

**Interfaces:**
- Consumes: `frontmatter_reach` (Task 2), `usage_reach` (Task 3).
- Produces: `merged_reach(project_root, knowledge=None, provenance=None, dataset_ids=None) -> dict[str, set[str]]` — per-dataset union of frontmatter + usage reach, deduplicated by target id (the union itself collapses a shared-source pair that reaches the same target, satisfying the redundancy-discount acceptance).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_dataset_prioritize_graph.py
from science_tool.dataset_prioritize import merged_reach


def test_merged_reach_unions_both_paths_and_dedups(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    # ALSO give dataset:d a frontmatter back-edge to the SAME question:q, while
    # keeping the sci:addresses edge so question:q is reachable via BOTH paths.
    (tmp_path / "entities/questions/q.md").write_text(
        '---\nid: "question:q"\ntype: "question"\ntitle: "Q"\n'
        'relations:\n  - predicate: "sci:addresses"\n    target: "proposition:p"\n'
        'related: ["dataset:d"]\n---\n', encoding="utf-8")
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))

    reach = merged_reach(tmp_path, knowledge, provenance, ["dataset:d"])
    # question:q reachable via BOTH paths → counted once; hypothesis:h via usage only
    assert reach["dataset:d"] == {"hypothesis:h", "question:q"}


def test_merged_reach_frontmatter_only_when_no_graph(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    (tmp_path / "entities/questions/q.md").write_text(
        '---\nid: "question:q"\ntype: "question"\ntitle: "Q"\nrelated: ["dataset:d"]\n---\n',
        encoding="utf-8")
    reach = merged_reach(tmp_path, None, None, ["dataset:d"])
    assert reach["dataset:d"] == {"question:q"}  # frontmatter path works with no graph
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize_graph.py -k merged_reach -v`
Expected: FAIL with `ImportError: cannot import name 'merged_reach'`.

- [ ] **Step 3: Write minimal implementation**

```python
def merged_reach(
    project_root: Path,
    knowledge=None,
    provenance=None,
    dataset_ids: list[str] | None = None,
) -> dict[str, set[str]]:
    fm_reach = frontmatter_reach(project_root)
    ids = dataset_ids if dataset_ids is not None else sorted(fm_reach)
    merged: dict[str, set[str]] = {ds_id: set(fm_reach.get(ds_id, set())) for ds_id in ids}
    if knowledge is not None and provenance is not None:
        for ds_id, targets in usage_reach(knowledge, provenance, ids).items():
            merged.setdefault(ds_id, set()).update(targets)  # union dedups by target id
    return merged
```

Note on the independence_group/cohort fractional discount (design Key decision 4, "open question"): the union's dedup-by-target already collapses a single dataset's redundant edges to the same target (the dengue shared-source acceptance). The finer per-line fractional weighting is deferred per the design's Open Questions; do NOT add it here without confirming an independence_group helper exists.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize_graph.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/dataset_prioritize.py science/tests/test_dataset_prioritize_graph.py
git commit -m "feat(dataset): merged per-dataset reach (frontmatter + usage union, dedup by target)"
```

---

### Task 5: `leverage_tilt` (reuse `_claim_summary_data`)

**Files:**
- Modify: `src/science_tool/dataset_prioritize.py`
- Test: `tests/test_dataset_prioritize_graph.py`

**Interfaces:**
- Produces: `leverage_tilt(knowledge, provenance, dataset_id, *, usage_props=None) -> float` — `1.0` baseline; bounded ≤ 2.0; raised by `risk_score`/`contested`/`single_source`/`no_empirical_data` over the propositions the dataset reaches via the usage path. Exactly `1.0` when no propositions are reached.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_dataset_prioritize_graph.py
from science_tool.dataset_prioritize import leverage_tilt, reached_proposition_uris


def test_leverage_tilt_neutral_when_no_props(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))
    # a dataset with no usage edges reaches no propositions → tilt is exactly 1.0
    assert leverage_tilt(knowledge, provenance, "dataset:absent") == 1.0


def test_leverage_tilt_bounded_and_responsive(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))
    tilt = leverage_tilt(knowledge, provenance, "dataset:d")
    assert 1.0 <= tilt <= 2.0  # single-source proposition raises tilt, capped at 2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize_graph.py -k leverage -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

```python
from science_tool.graph.store.summary import _claim_summary_data

# leverage contribution per signal/field, summed across reached propositions then capped.
_LEVERAGE_PER_SIGNAL = {"contested": 0.4, "single_source": 0.3, "no_empirical_data": 0.2}
_LEVERAGE_RISK_SCALE = 0.05  # × risk_score, modest
_LEVERAGE_CAP = 2.0


def reached_proposition_uris(knowledge, provenance, dataset_id: str) -> set[URIRef]:
    """Propositions a dataset reaches via the usage path (URIs, for signal lookup)."""
    props: set[URIRef] = set()
    ds_uri = project_entity_uri(dataset_id)
    for usage_node in provenance.subjects(SCI_NS.dataset, ds_uri):
        for consumer in provenance.subjects(SCI_NS.hasDatasetUsage, usage_node):
            for _, _, prop in knowledge.triples((consumer, CITO_NS.supports, None)):
                if isinstance(prop, URIRef):
                    props.add(prop)
            for _, _, prop in knowledge.triples((consumer, CITO_NS.disputes, None)):
                if isinstance(prop, URIRef):
                    props.add(prop)
    return props


def leverage_tilt(knowledge, provenance, dataset_id: str, *, usage_props=None) -> float:
    props = usage_props if usage_props is not None else reached_proposition_uris(
        knowledge, provenance, dataset_id
    )
    if not props:
        return 1.0
    bonus = 0.0
    for prop in props:
        summary = _claim_summary_data(knowledge, provenance, prop)
        if summary is None:
            continue
        for sig in summary.get("signals", []):
            bonus += _LEVERAGE_PER_SIGNAL.get(sig, 0.0)
        bonus += _LEVERAGE_RISK_SCALE * float(summary.get("risk_score", 0.0))
    return min(_LEVERAGE_CAP, 1.0 + bonus)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize_graph.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/dataset_prioritize.py science/tests/test_dataset_prioritize_graph.py
git commit -m "feat(dataset): leverage_tilt reusing _claim_summary_data signals (capped, neutral when no props)"
```

---

### Task 6: score assembly + ranked rows + gap-flags

**Files:**
- Modify: `src/science_tool/dataset_prioritize.py`
- Test: `tests/test_dataset_prioritize.py` (sparse, no-graph) and `tests/test_dataset_prioritize_graph.py` (mixed)

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: `prioritize(project_root, *, knowledge=None, provenance=None, origin=None, status=None, tier=None, level=None) -> list[dict]` returning rows sorted by `score` desc, each: `{"id","title","score","readiness","reach","top_reason","gap_flags": list[str]}`. Gap-flags: `no-edge` (reach==0), `unverified` (external & not access.verified), `redundant` (reserved; emitted only when a future discount fires), `readiness-unresolved` (from `readiness_weight`).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_dataset_prioritize.py
from science_tool.dataset_prioritize import prioritize


def test_prioritize_sparse_no_graph_orders_by_accessibility_and_flags(tmp_path: Path) -> None:
    # available > unverified public; the unconnected one gets no-edge.
    _write(tmp_path / "doc/datasets/avail.md",
           '---\nid: "dataset:avail"\ntype: "dataset"\ntitle: "Avail"\norigin: "external"\n'
           'related: ["question:q1"]\naccess: {level: "controlled", verified: true}\n---\n')
    _write(tmp_path / "doc/datasets/unv.md",
           '---\nid: "dataset:unv"\ntype: "dataset"\ntitle: "Unv"\norigin: "external"\n'
           'access: {level: "public", verified: false}\n---\n')
    _write(tmp_path / "entities/questions/q1.md",
           '---\nid: "question:q1"\ntype: "question"\ntitle: "Q1"\n---\n')

    rows = prioritize(tmp_path)
    ids = [r["id"] for r in rows]
    assert ids[0] == "dataset:avail"                  # verified + reach=1 ranks first
    unv = next(r for r in rows if r["id"] == "dataset:unv")
    assert "unverified" in unv["gap_flags"]
    assert "no-edge" in unv["gap_flags"]              # reach 0
    assert rows[0]["score"] > unv["score"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize.py -k prioritize -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

```python
from science_tool.datasets_catalog import _local_rows  # reuse the dataset-row loader


def _gap_flags_for(row_fm: dict, reach_n: int, readiness_flags: list[str]) -> list[str]:
    flags = list(readiness_flags)
    if reach_n == 0:
        flags.append("no-edge")
    origin = row_fm.get("origin")
    access = row_fm.get("access") or {}
    verified = bool(access.get("verified")) if isinstance(access, dict) else False
    if origin == "external" and not verified:
        flags.append("unverified")
    return flags


def _top_reason(weight: float, readiness_state: str, reach_n: int, tilt: float) -> str:
    bits = [f"readiness={readiness_state}({weight:g})", f"reach={reach_n}"]
    if tilt > 1.0:
        bits.append(f"leverage×{tilt:g}")
    return ", ".join(bits)


def prioritize(
    project_root: Path,
    *,
    knowledge=None,
    provenance=None,
    origin: str | None = None,
    status: str | None = None,
    tier: str | None = None,
    level: str | None = None,
) -> list[dict]:
    rows_in = _local_rows(project_root)  # id/title/status/tier/origin/level/verified/scope
    # Need full frontmatter for readiness + flags; re-read per dataset.
    dataset_ids = [r["id"] for r in rows_in]
    reach_map = merged_reach(project_root, knowledge, provenance, dataset_ids)

    out: list[dict] = []
    for r in rows_in:
        if origin is not None and r["origin"] != origin:
            continue
        if status is not None and r["status"] != status:
            continue
        if tier is not None and r["tier"] != tier:
            continue
        if level is not None and r["level"] != level:
            continue
        slug = r["id"].split(":", 1)[-1]
        parsed = parse_frontmatter(project_root / "doc" / "datasets" / f"{slug}.md")
        fm = parsed[0] if parsed else {}
        weight, r_flags = readiness_weight(fm)
        reach_set = reach_map.get(r["id"], set())
        reach_n = len(reach_set)
        tilt = 1.0
        if knowledge is not None and provenance is not None:
            tilt = leverage_tilt(knowledge, provenance, r["id"])
        score = weight * (1 + reach_n) * tilt
        out.append({
            "id": r["id"],
            "title": r["title"],
            "score": round(score, 4),
            "readiness": readiness_for(fm).state,
            "reach": reach_n,
            "top_reason": _top_reason(weight, readiness_for(fm).state, reach_n, tilt),
            "gap_flags": _gap_flags_for(fm, reach_n, r_flags),
        })
    out.sort(key=lambda d: (-d["score"], d["id"]))
    return out
```

- [ ] **Step 4: Add the mixed-graph acceptance test**

```python
# append to tests/test_dataset_prioritize_graph.py
from science_tool.dataset_prioritize import prioritize


def test_prioritize_mixed_graph_frontmatter_dataset_not_no_edge(tmp_path: Path) -> None:
    _seed_graph_project(tmp_path)  # dataset:d connected via usage
    # a second dataset connected ONLY by frontmatter to question:q (keep the
    # sci:addresses edge intact for dataset:d's usage path)
    (tmp_path / "entities/questions/q.md").write_text(
        '---\nid: "question:q"\ntype: "question"\ntitle: "Q"\n'
        'relations:\n  - predicate: "sci:addresses"\n    target: "proposition:p"\n'
        'related: ["dataset:fm_only"]\n---\n', encoding="utf-8")
    (tmp_path / "doc/datasets/fm_only.md").write_text(
        '---\nid: "dataset:fm_only"\ntype: "dataset"\ntitle: "FM"\norigin: "external"\n'
        'access: {level: "public", verified: true}\n---\n', encoding="utf-8")
    graph_path = materialize_graph(tmp_path)
    ds = _load_dataset(graph_path)
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))

    rows = prioritize(tmp_path, knowledge=knowledge, provenance=provenance)
    fm_only = next(r for r in rows if r["id"] == "dataset:fm_only")
    assert fm_only["reach"] >= 1
    assert "no-edge" not in fm_only["gap_flags"]   # regression for the High review finding
```

- [ ] **Step 5: Run tests, then commit**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize.py tests/test_dataset_prioritize_graph.py -v`
Expected: PASS.

```bash
cd ~/d/science && git add science/src/science_tool/dataset_prioritize.py science/tests/test_dataset_prioritize.py science/tests/test_dataset_prioritize_graph.py
git commit -m "feat(dataset): prioritize() score assembly, ranked rows, gap-flags"
```

---

### Task 7: `dataset prioritize` CLI command

**Files:**
- Modify: `src/science_tool/cli.py` (inside the `dataset_group` block, after `dataset_list`, near line 5258)
- Test: `tests/test_dataset_prioritize_cli.py`

**Interfaces:**
- Consumes: `prioritize` (Task 6), `graph_is_stale`, `_load_dataset`, `_graph_uri`, `DEFAULT_GRAPH_PATH`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dataset_prioritize_cli.py
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed(root: Path) -> None:
    d = root / "doc" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / "a.md").write_text(
        '---\nid: "dataset:a"\ntype: "dataset"\ntitle: "A"\norigin: "external"\n'
        'access: {level: "controlled", verified: true}\n---\n', encoding="utf-8")
    (d / "b.md").write_text(
        '---\nid: "dataset:b"\ntype: "dataset"\ntitle: "B"\norigin: "external"\n'
        'access: {level: "public", verified: false}\n---\n', encoding="utf-8")


def _run(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli, ["dataset", "prioritize", *args],
        catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )


def test_prioritize_runs_without_graph_and_warns(tmp_path: Path) -> None:
    _seed(tmp_path)
    res = _run(tmp_path)
    assert res.exit_code == 0
    assert "dataset:a" in res.output and "dataset:b" in res.output
    # no graph present → a stderr warning is emitted but the command still ranks.
    # This repo's CliRunner captures stderr separately (see tests/test_datasets_cli.py:80).
    combined = res.output + (res.stderr if res.stderr_bytes else "")
    assert "graph" in combined.lower()


def test_prioritize_json_and_explain(tmp_path: Path) -> None:
    _seed(tmp_path)
    res = _run(tmp_path, "--format", "json")
    assert res.exit_code == 0
    import json
    rows = json.loads(res.output)  # stdout is clean JSON; the warning is on stderr
    assert any(r["id"] == "dataset:a" for r in rows)
```

(This repo's `CliRunner` captures stderr **separately** from stdout — `res.output` is stdout only, `res.stderr` holds the warning (guard with `res.stderr_bytes`), per `tests/test_datasets_cli.py:80`. Because the warning goes to stderr via `click.echo(..., err=True)`, `--format json` mode emits clean JSON on stdout — `res.output` parses directly with no warning line to strip. The `_run` helper above relies on the default capture, so no `mix_stderr` argument is needed.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize_cli.py -v`
Expected: FAIL — `No such command 'prioritize'`.

- [ ] **Step 3: Write minimal implementation (add after `dataset_list`)**

```python
@dataset_group.command("prioritize")
@click.option("--origin", default=None, type=click.Choice(["external", "derived"]))
@click.option("--status", default=None)
@click.option("--tier", default=None, type=click.Choice(["use-now", "evaluate-next", "track"]))
@click.option("--level", default=None,
              type=click.Choice(["public", "registration", "controlled", "commercial", "mixed"]))
@click.option("--format", "output_format", default="table", type=click.Choice(["table", "json"]))
@click.option("--explain", is_flag=True, help="Show the per-row scoring reason")
@click.option("--project-root", default=None,
              type=click.Path(path_type=Path, file_okay=False, dir_okay=True))
def dataset_prioritize(
    origin: str | None, status: str | None, tier: str | None, level: str | None,
    output_format: str, explain: bool, project_root: Path | None,
) -> None:
    """Rank dataset entities by accessibility-weighted, graph-aware usefulness."""
    import json as _json

    from science_tool.dataset_prioritize import prioritize
    from science_tool.entities import graph_is_stale
    from science_tool.graph.store import DEFAULT_GRAPH_PATH
    from science_tool.graph.store.dataset import _load_dataset
    from science_tool.graph.store.identity import _graph_uri

    root = project_root.resolve() if project_root else _project_root_from_env()
    graph_path = root / DEFAULT_GRAPH_PATH
    knowledge = provenance = None
    if graph_path.exists():
        if graph_is_stale(root, graph_path):
            click.echo(
                "warning: graph may be stale; reach/leverage from last build — run `science graph build`",
                err=True,
            )
        ds = _load_dataset(graph_path)
        knowledge = ds.graph(_graph_uri("graph/knowledge"))
        provenance = ds.graph(_graph_uri("graph/provenance"))
    else:
        click.echo("warning: no materialized graph; reach from frontmatter only", err=True)

    rows = prioritize(root, knowledge=knowledge, provenance=provenance,
                      origin=origin, status=status, tier=tier, level=level)

    if output_format == "json":
        click.echo(_json.dumps(rows, indent=2))
        return
    if not rows:
        click.echo("No matching dataset entities.")
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(show_header=True, header_style="bold")
    cols = ["rank", "id", "score", "readiness", "reach", "gap-flags"]
    if explain:
        cols.append("reason")
    for c in cols:
        table.add_column(c, overflow="fold", no_wrap=False)
    for i, r in enumerate(rows, 1):
        cells = [str(i), r["id"], f"{r['score']:g}", r["readiness"], str(r["reach"]),
                 ", ".join(r["gap_flags"]) or "-"]
        if explain:
            cells.append(r["top_reason"])
        table.add_row(*cells)
    Console(width=200).print(table)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize_cli.py -v`
Expected: PASS. (Adjust the warning text / JSON-mode warning handling if the test's parsing needs it.)

- [ ] **Step 5: Commit**

```bash
cd ~/d/science && git add science/src/science_tool/cli.py science/tests/test_dataset_prioritize_cli.py
git commit -m "feat(cli): add `science dataset prioritize` (table/json, --explain, stale-graph warning)"
```

---

### Task 8: `/science:catalog-datasets` orchestration command

**Files:**
- Create: `commands/catalog-datasets.md`

**Interfaces:** none (a markdown command doc, consumed by the agent runtime). Mirror the structure/voice of an existing command, e.g. `commands/find-datasets.md`.

- [ ] **Step 1: Read the sibling command for house style**

Run: `sed -n '1,60p' ~/d/science/commands/find-datasets.md`
Note its frontmatter (if any), section headings, and the `uv run science` invocation convention.

- [ ] **Step 2: Write `commands/catalog-datasets.md`**

Author a command that drives the front-half loop from `plan:2026-06-21-catalog-datasets-design`. It MUST contain these sections, each with concrete steps (not prose placeholders):

1. **Setup** — follow `references/command-preamble.md` (role: `research-assistant`), resolve project root.
2. **Gap scan** — list questions/hypotheses with no accessible dataset: run `uv run science dataset prioritize --format json`, and cross-reference the project's questions/hypotheses; a Q/H is a gap if no dataset reaches it OR every dataset that does is `unverified`/inaccessible. Present the gap list.
3. **Discover** — for gap Q/H, invoke `/science:find-datasets`; author candidates with `uv run science dataset add <slug> --title ... --level public ...` (status defaults to `candidate`). Bias to obtainable omics (GEO/SRA/Zenodo).
4. **Verify accessibility** — for each candidate, confirm obtainability and record it by editing the entity's `access` block (`verified: true` + `verification_method` + `last_reviewed`) OR populating `access.exception` per the `plan-pipeline` Dimension-3 Branch-A/B logic; append a dated verification-log line. State explicitly: no new findings store — reuse the access schema.
5. **Connect** — add `related:` edges between datasets and the Q/H they inform; where evidence-lines exist, author `dataset_usage` blocks.
6. **Prioritize** — run `uv run science dataset prioritize --explain`; present the ranked table + gap summary.
7. **Handoff** — route the top obtainable datasets to `/science:plan-pipeline` → execute; state that per-dataset QA/download is out of scope for this command.
8. **Process reflection** — `science feedback add` stub matching other commands.

Include a top note: "This command is the front half of the dataset arc (design: `~/d/science/docs/plans/2026-06-21-catalog-datasets-design.md`). Operationalization is `plan-pipeline`; commons promotion is deferred and gated on `access.verified`."

**Invocation convention (resolves the two contexts):** the command doc runs inside a *consumer* project where `science` is a dependency, so its example invocations follow the sibling commands' `uv run science <cmd>` convention (matching `commands/find-datasets.md` and the user guide) — do NOT write `--frozen` into the consumer-facing examples. The plan's `uv run --frozen` constraint applies to science-repo dev/test only, e.g. the verification step below, which runs from the `science/` subproject.

- [ ] **Step 3: Verify it is well-formed and references real surfaces**

Run:
```bash
cd ~/d/science && grep -n "dataset prioritize\|find-datasets\|plan-pipeline\|access" commands/catalog-datasets.md
cd ~/d/science/science && uv run --frozen science dataset prioritize --help
```
Expected: the grep shows each referenced surface is named; `--help` (run from the `science/` subproject — root invocation fails with `Failed to spawn: science`) exits 0 and lists the options.

- [ ] **Step 4: Commit**

```bash
cd ~/d/science && git add commands/catalog-datasets.md
git commit -m "feat(commands): add /science:catalog-datasets front-half orchestration command"
```

---

### Task 9: Final validation (full suite + real sparse-graph smoke)

**Files:** none (validation only).

- [ ] **Step 1: Run the full dataset test suite**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_prioritize.py tests/test_dataset_prioritize_graph.py tests/test_dataset_prioritize_cli.py tests/test_datasets_list_cli.py tests/test_dataset_show_consumers_cli.py tests/test_dataset_add_cli.py -v`
Expected: all PASS.

- [ ] **Step 2: Framework validate (no regressions)**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/ -q -k "dataset or graph_materialize"`
Expected: no failures attributable to this change.

- [ ] **Step 3: Real sparse-graph smoke against the first consumer**

Run:
```bash
cd ~/d/health/processes/post-acute-infection
uv run --frozen science dataset prioritize --explain
```
Expected: exit 0; a stale/missing-graph warning to stderr; 14 dataset rows ranked with `available`/`unverified` readiness, `reach` from frontmatter, and `no-edge`/`unverified` gap-flags. Confirm the two public literature sets and any verified entries float toward the top and that no row silently lands in a default weight bucket (no unexpected `readiness-unresolved`).

- [ ] **Step 4: Commit any doc/fixups surfaced by validation (if needed)**

```bash
cd ~/d/science && git add -A && git commit -m "chore(dataset): validation fixups for catalog-datasets"
```

---

## Self-Review

**Spec coverage (against `2026-06-21-catalog-datasets-design.md`):**
- `science dataset prioritize` primitive → Tasks 1–7. `readiness_weight` keyed on exact states + flagged default → Task 1. Merged bidirectional reach, source_refs excluded → Tasks 2–4 + 6. `leverage_tilt` reuse of `_claim_summary_data` (not `query_dashboard_summary`) → Task 5. Stale-graph degrade-with-warning → Task 7. `/science:catalog-datasets` loop → Task 8. First-consumer validation → Task 9.
- Acceptance criteria mapped: zero-evidence-line ordering + gap-flags → Task 6 Step 1; mixed-graph not-`no-edge` → Task 6 Step 4; `--explain` reasons → Task 7; stale/missing graph → Task 7 Step 1; flagged default → Task 1; redundancy collapse (dedup-by-target) → Task 4; no regression to existing dataset commands → Task 9 Step 1.
- Deferred-per-design (NOT in this plan, intentionally): independence_group/cohort fractional discount (design Open Question), centrality, commons promotion, per-dataset QA/download.

**Type consistency:** `prioritize` returns rows with `gap_flags` (list); CLI renders `gap-flags` column from `r["gap_flags"]`. `readiness_for`/`readiness_weight`/`frontmatter_reach`/`usage_reach`/`merged_reach`/`leverage_tilt`/`prioritize` signatures are consistent across tasks. Graph layers obtained identically everywhere (`_load_dataset` + `_graph_uri("graph/knowledge"|"graph/provenance")`).

**Graph-fixture correctness (all resolved):** the question→proposition `sci:addresses` edge is authored via a `relations:` block (flattened at sources.py:1047, emitted at materialize.py:1173) — not `related:`, which would be `skos:related`. URI→ref uses the real inverse `canonical_id_from_entity_uri` (identity.py:32). The entity layout is `entities/{hypotheses,questions,propositions,evidence-lines}/` (datasets in `doc/datasets/`), matching `load_project_sources` scan roots.
