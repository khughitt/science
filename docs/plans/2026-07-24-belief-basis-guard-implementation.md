# Belief-Basis Guard Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the observable the autonomy envelope's semantic gate is defined over — capture a per-entity *belief basis* from a materialized graph, digest it, and compare two captures into a typed delta.

**Architecture:** One new pure module, `graph/belief_basis.py`, plus one CLI subcommand. Capture takes two `rdflib.Graph` objects (knowledge, provenance) rather than a `Dataset`, matching how `collect_evidence_units` is already tested, so every function is unit-testable without building a project. Basis capture reuses the exact per-entity recipe already used by the attention instrument (`graph/attention.py:350-353`): expand the target closure, collect evidence units, record policy identity. It deliberately does **not** call `aggregate_belief` — the whole point is to compare inputs, not the aggregated verdict.

**Tech Stack:** Python 3.12+, pydantic v2, rdflib, click, pytest. Package root is `science/` (`science/pyproject.toml`); there is no root `pyproject.toml`.

## Global Constraints

- The basis is **target closure + raw evidence-unit multiset + policy identity**. Never merely the final ordinal magnitude — a run whose units change but cancel must be detectable.
- An uncomputable basis yields `InstrumentResult.unwired`. **`unwired` never means clean.**
- `belief_scalar` / `belief_scalar_enabled` must NOT be consulted anywhere in this plan. It is opt-in and returns `False` when unconfigured, so a gate defined over it fails open. It is an *additional* comparison only, and lands in Plan D.
- All commands run from `science/`: `cd science && uv run --frozen pytest`, `uv run ruff check`, `uv run pyright`.
- Pyright is configured once by the repo-root `pyrightconfig.json`; do not add a `[tool.pyright]` block.
- Conventional commits. **No AI-attribution trailer or footer on any commit.**
- Composition over inheritance; explicit over defensive; fail early rather than silent fallback.

---

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/graph/belief_basis.py` | **Create.** Basis capture, unit keying, digest, comparison. Pure — no filesystem, no project config. |
| `science/src/science_tool/graph/cli.py` | **Modify.** Add the `belief-basis` subcommand to the existing `graph_group`. |
| `science/tests/test_belief_basis.py` | **Create.** Unit tests for keying, capture, digest, comparison. |
| `science/tests/test_belief_basis_cli.py` | **Create.** CLI tests: snapshot round-trip and the three exit codes. |

`belief_basis.py` sits beside `belief.py`, `belief_policy.py`, and `belief_scalar.py` because it changes when belief changes — that is the coupling that matters.

---

### Task 1: Canonical evidence-unit key

**Files:**
- Create: `science/src/science_tool/graph/belief_basis.py`
- Test: `science/tests/test_belief_basis.py`

**Interfaces:**
- Consumes: `EvidenceUnit` from `science_tool.graph.belief` (a dataclass; fields at `graph/belief.py:20-40`).
- Produces: `unit_key(unit: EvidenceUnit) -> str`.

The key is built from `dataclasses.asdict` rather than a hand-listed field subset. This is the load-bearing property: when someone adds a new field to `EvidenceUnit`, it enters the key automatically, so an unrecognized belief input changes the basis instead of being silently omitted from it. A hand-listed subset would fail open on exactly the change most likely to matter.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_belief_basis.py
from __future__ import annotations

import dataclasses

from science_tool.graph.belief import EvidenceUnit
from science_tool.graph.belief_basis import unit_key


def _u(stance: str = "supports", **kw) -> EvidenceUnit:
    base = dict(
        line_uri="x", stance=stance, strength="strong", independence="independent",
        independence_group="g", evidence_role="direct_test",
        evidence_type="empirical_data_evidence", dispute_scope=None,
        proxy_directness=None, has_measurement_model=False, source=None,
        observability_keys=(),
    )
    base.update(kw)
    return EvidenceUnit(**base)


def test_identical_units_share_a_key():
    assert unit_key(_u()) == unit_key(_u())


def test_differing_strength_changes_the_key():
    assert unit_key(_u(strength="strong")) != unit_key(_u(strength="weak"))


def test_key_covers_every_evidence_unit_field():
    """Fail-closed: the key must be derived from the dataclass, not a hand-listed subset.

    A new EvidenceUnit field must enter the basis automatically. This test fails
    the moment someone rewrites unit_key against an explicit field list.
    """
    key = unit_key(_u())
    for field in dataclasses.fields(EvidenceUnit):
        assert field.name in key, f"{field.name} missing from unit key"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.graph.belief_basis'`

- [ ] **Step 3: Write the minimal implementation**

```python
# science/src/science_tool/graph/belief_basis.py
"""Belief-basis capture and comparison — the observable the autonomy semantic gate compares.

The basis is deliberately the *inputs* to belief, not the aggregated verdict: a run
whose evidence units change but happen to cancel leaves the ordinal magnitude intact
and must still be detected.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from science_tool.graph.belief import EvidenceUnit


def unit_key(unit: EvidenceUnit) -> str:
    """Canonical, comparable key for one evidence unit.

    Derived from `asdict` so a NEW field on EvidenceUnit enters the key automatically.
    Never rewrite this against an explicit field list: an unrecognized belief input
    must change the basis rather than be silently dropped from it.
    """
    return json.dumps(asdict(unit), sort_keys=True, default=str)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief_basis.py science/tests/test_belief_basis.py
git commit -m "feat(graph): add canonical evidence-unit key for belief basis"
```

---

### Task 2: Per-entity basis capture

**Files:**
- Modify: `science/src/science_tool/graph/belief_basis.py`
- Test: `science/tests/test_belief_basis.py`

**Interfaces:**
- Consumes: `unit_key` (Task 1); `collect_evidence_units(knowledge, provenance, targets)` (`graph/belief.py:123`); `_evidence_targets_for_uri(knowledge, target_uri)` and `canonical_id_from_entity_uri(uri)` — both imported from `science_tool.graph.store`, the same path `graph/attention.py:22` uses; `DEFAULT_BELIEF_POLICY` (`graph/belief_policy.py:99`); `InstrumentResult` (`science_tool/instruments.py:74`).
- Produces: `class EntityBasis` (frozen pydantic model with fields `entity_id: str`, `uri: str`, `target_uris: tuple[str, ...]`, `unit_keys: tuple[str, ...]`, `policy_id: str`, `policy_version: str`); `capture_basis(knowledge, provenance, *, policy=DEFAULT_BELIEF_POLICY) -> InstrumentResult[EntityBasis]`; the constant `NO_TYPED_ENTITIES = "no_typed_entities"`.

The `unwired` precondition matters as much as the happy path. A graph carrying no typed project entities has not been assessed for belief at all — reporting "no changes" there would present an unbuilt graph as a clean one, which is the exact failure `InstrumentResult` exists to prevent.

`canonical_id_from_entity_uri` returns `None` for non-entity URIs — external CURIEs, source URIs, and layer URIs like `graph/knowledge` (`graph/store/identity.py:32-50`). That is the entity filter; do not write a second one.

- [ ] **Step 1: Write the failing tests**

```python
# append to science/tests/test_belief_basis.py
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from science_tool.graph.belief import EVIDENCE_LINE_CLASS
from science_tool.graph.belief_basis import NO_TYPED_ENTITIES, capture_basis
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS

CLAIM = URIRef(PROJECT_NS["proposition/p"])
LINE = URIRef(PROJECT_NS["evidence-line/e"])


def _graphs_with_one_supporting_line() -> tuple[Graph, Graph]:
    knowledge, provenance = Graph(), Graph()
    knowledge.add((CLAIM, RDF.type, SCI_NS.Proposition))
    knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
    knowledge.add((LINE, CITO_NS.supports, CLAIM))
    provenance.add((LINE, SCI_NS.evidenceStrength, Literal("strong")))
    return knowledge, provenance


def test_capture_records_one_unit_for_the_claim():
    knowledge, provenance = _graphs_with_one_supporting_line()
    result = capture_basis(knowledge, provenance)
    assert result.status == "ok"
    claim = next(r for r in result.rows if r.entity_id == "proposition:p")
    assert len(claim.unit_keys) == 1
    assert claim.target_uris == (str(CLAIM),)


def test_capture_records_policy_identity():
    knowledge, provenance = _graphs_with_one_supporting_line()
    claim = next(r for r in capture_basis(knowledge, provenance).rows if r.entity_id == "proposition:p")
    assert claim.policy_id == "core-default"
    assert claim.policy_version


def test_empty_graph_is_unwired_not_empty():
    """No typed entities means belief was never assessed — that is not 'no changes'."""
    result = capture_basis(Graph(), Graph())
    assert result.status == "unwired"
    assert result.code == NO_TYPED_ENTITIES


def test_layer_uris_are_not_entities():
    knowledge, provenance = Graph(), Graph()
    knowledge.add((URIRef(PROJECT_NS["graph/knowledge"]), RDF.type, SCI_NS.Layer))
    assert capture_basis(knowledge, provenance).status == "unwired"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis.py -v`
Expected: FAIL — `ImportError: cannot import name 'NO_TYPED_ENTITIES'`

- [ ] **Step 3: Write the minimal implementation**

```python
# add to science/src/science_tool/graph/belief_basis.py

from pydantic import BaseModel, ConfigDict
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from science_tool.graph.belief import collect_evidence_units
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY, BeliefPolicy
from science_tool.graph.store import _evidence_targets_for_uri, canonical_id_from_entity_uri
from science_tool.instruments import InstrumentResult

#: The sole precondition of basis capture. With no typed project entity in
#: graph/knowledge, NO entity has been assessed and the basis is not a basis.
NO_TYPED_ENTITIES = "no_typed_entities"


class EntityBasis(BaseModel):
    """The belief inputs for one entity, in comparable canonical form."""

    model_config = ConfigDict(frozen=True)

    entity_id: str
    uri: str
    target_uris: tuple[str, ...]
    unit_keys: tuple[str, ...]
    policy_id: str
    policy_version: str


def capture_basis(
    knowledge: Graph,
    provenance: Graph,
    *,
    policy: BeliefPolicy = DEFAULT_BELIEF_POLICY,
) -> InstrumentResult[EntityBasis]:
    """Capture the belief basis of every typed project entity in `knowledge`.

    Uses the same per-entity recipe as the attention instrument
    (`graph/attention.py:350-353`), but stops at the units: the basis compares
    belief INPUTS, never the aggregated magnitude.
    """
    entity_uris = sorted({str(s) for s in knowledge.subjects(RDF.type, None) if canonical_id_from_entity_uri(str(s))})
    if not entity_uris:
        return InstrumentResult.unwired(
            code=NO_TYPED_ENTITIES,
            reason=("graph/knowledge carries no typed project entities; no belief basis was computed. Run `science graph build` first."),
        )

    rows: list[EntityBasis] = []
    for uri in entity_uris:
        targets = _evidence_targets_for_uri(knowledge, URIRef(uri))
        units = collect_evidence_units(knowledge, provenance, targets)
        canonical = canonical_id_from_entity_uri(uri)
        assert canonical is not None  # filtered above
        rows.append(
            EntityBasis(
                entity_id=canonical,
                uri=uri,
                target_uris=tuple(sorted(str(t) for t in targets)),
                unit_keys=tuple(sorted(unit_key(u) for u in units)),
                policy_id=policy.policy_id,
                policy_version=policy.version,
            )
        )
    return InstrumentResult.from_rows(rows)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief_basis.py science/tests/test_belief_basis.py
git commit -m "feat(graph): capture per-entity belief basis with unwired precondition"
```

---

### Task 3: Basis digest

**Files:**
- Modify: `science/src/science_tool/graph/belief_basis.py`
- Test: `science/tests/test_belief_basis.py`

**Interfaces:**
- Consumes: `EntityBasis` (Task 2).
- Produces: `basis_digest(bases: Iterable[EntityBasis]) -> str` — a hex sha256.

The run record persists this digest so a later validation can prove it compared against the same starting state (spec §2, `basis_digest`). It must be order-independent, because entity iteration order is not a contract.

- [ ] **Step 1: Write the failing tests**

```python
# append to science/tests/test_belief_basis.py
from science_tool.graph.belief_basis import EntityBasis, basis_digest


def _basis(entity_id: str, unit_keys: tuple[str, ...] = ()) -> EntityBasis:
    return EntityBasis(
        entity_id=entity_id,
        uri=str(PROJECT_NS[entity_id.replace(":", "/")]),
        target_uris=(),
        unit_keys=unit_keys,
        policy_id="core-default",
        policy_version="1",
    )


def test_digest_is_order_independent():
    a, b = _basis("proposition:a"), _basis("proposition:b")
    assert basis_digest([a, b]) == basis_digest([b, a])


def test_digest_changes_when_a_unit_changes():
    before = basis_digest([_basis("proposition:a", ("k1",))])
    after = basis_digest([_basis("proposition:a", ("k2",))])
    assert before != after


def test_digest_of_nothing_is_stable():
    assert basis_digest([]) == basis_digest([])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis.py -k digest -v`
Expected: FAIL — `ImportError: cannot import name 'basis_digest'`

- [ ] **Step 3: Write the minimal implementation**

```python
# add to science/src/science_tool/graph/belief_basis.py
import hashlib
from typing import Iterable


def basis_digest(bases: Iterable[EntityBasis]) -> str:
    """Order-independent sha256 over a whole capture.

    Persisted in the run record so a later validation can prove it compared
    against the same starting state.
    """
    payload = json.dumps(
        [b.model_dump(mode="json") for b in sorted(bases, key=lambda b: b.uri)],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief_basis.py science/tests/test_belief_basis.py
git commit -m "feat(graph): add order-independent belief-basis digest"
```

---

### Task 4: Basis comparison

**Files:**
- Modify: `science/src/science_tool/graph/belief_basis.py`
- Test: `science/tests/test_belief_basis.py`

**Interfaces:**
- Consumes: `EntityBasis` (Task 2).
- Produces: `class BasisDelta` (frozen pydantic model with `entity_id: str`, `changed: tuple[str, ...]`, `detail: str`); `compare_bases(before: Iterable[EntityBasis], after: Iterable[EntityBasis]) -> list[BasisDelta]`.

Comparison semantics come straight from the spec and each one is a deliberate choice:

- **Pre-existing entity, basis differs** → delta. `changed` holds any of `"targets"`, `"units"`, `"policy"`.
- **Entity only in `after`** → **no delta**. A new entity has no before-value, so an autonomous run may file a question or a task. Anything that new entity does to an *existing* entity's belief shows up as a delta on that existing entity, which is where the guard belongs.
- **Entity only in `before`** → delta with `changed=("removed",)`. Deleting an entity can move belief elsewhere, and silence about it would be a hole.

- [ ] **Step 1: Write the failing tests**

```python
# append to science/tests/test_belief_basis.py
from science_tool.graph.belief_basis import compare_bases


def test_identical_captures_have_no_delta():
    before = [_basis("proposition:a", ("k1",))]
    assert compare_bases(before, list(before)) == []


def test_changed_units_are_reported():
    deltas = compare_bases([_basis("proposition:a", ("k1",))], [_basis("proposition:a", ("k2",))])
    assert [d.entity_id for d in deltas] == ["proposition:a"]
    assert deltas[0].changed == ("units",)


def test_new_entity_is_not_a_delta():
    """A bot filing a new question is permitted; it has no before-value to move."""
    assert compare_bases([], [_basis("question:0042")]) == []


def test_removed_entity_is_a_delta():
    deltas = compare_bases([_basis("proposition:a")], [])
    assert deltas[0].changed == ("removed",)


def test_policy_swap_is_a_delta_even_with_identical_units():
    before = [_basis("proposition:a", ("k1",))]
    after = [
        EntityBasis(
            entity_id="proposition:a", uri=str(PROJECT_NS["proposition/a"]),
            target_uris=(), unit_keys=("k1",),
            policy_id="other-policy", policy_version="1",
        )
    ]
    assert compare_bases(before, after)[0].changed == ("policy",)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis.py -k compare -v`
Expected: FAIL — `ImportError: cannot import name 'compare_bases'`

- [ ] **Step 3: Write the minimal implementation**

```python
# add to science/src/science_tool/graph/belief_basis.py


class BasisDelta(BaseModel):
    """One pre-existing entity whose belief basis moved."""

    model_config = ConfigDict(frozen=True)

    entity_id: str
    changed: tuple[str, ...]
    detail: str


def compare_bases(before: Iterable[EntityBasis], after: Iterable[EntityBasis]) -> list[BasisDelta]:
    """Deltas for PRE-EXISTING entities only.

    An entity present only in `after` is new and yields no delta — it had no
    before-value. Its effect on any existing entity surfaces as a delta on that
    entity. An entity present only in `before` was removed, which can move belief
    elsewhere and is reported.
    """
    before_by_id = {b.entity_id: b for b in before}
    after_by_id = {a.entity_id: a for a in after}

    deltas: list[BasisDelta] = []
    for entity_id in sorted(before_by_id):
        old = before_by_id[entity_id]
        new = after_by_id.get(entity_id)
        if new is None:
            deltas.append(
                BasisDelta(entity_id=entity_id, changed=("removed",), detail="entity present before the run, absent after")
            )
            continue
        changed: list[str] = []
        if old.target_uris != new.target_uris:
            changed.append("targets")
        if old.unit_keys != new.unit_keys:
            changed.append("units")
        if (old.policy_id, old.policy_version) != (new.policy_id, new.policy_version):
            changed.append("policy")
        if changed:
            deltas.append(
                BasisDelta(
                    entity_id=entity_id,
                    changed=tuple(changed),
                    detail=(
                        f"targets {len(old.target_uris)}->{len(new.target_uris)}, "
                        f"units {len(old.unit_keys)}->{len(new.unit_keys)}, "
                        f"policy {old.policy_id}/{old.policy_version}->{new.policy_id}/{new.policy_version}"
                    ),
                )
            )
    return deltas
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis.py -v`
Expected: PASS (15 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief_basis.py science/tests/test_belief_basis.py
git commit -m "feat(graph): compare belief bases into typed per-entity deltas"
```

---

### Task 5: `science graph belief-basis` command

**Files:**
- Modify: `science/src/science_tool/graph/cli.py`
- Test: `science/tests/test_belief_basis_cli.py`

**Interfaces:**
- Consumes: `capture_basis`, `basis_digest`, `compare_bases`, `EntityBasis` (Tasks 2-4); `load_trig_dataset_preserving_literals(graph_path)` (`graph/trig.py`, used the same way at `wander/sampling.py:37`); `graph_uri(layer)` (`graph/store/identity.py:63`).
- Produces: a `belief-basis` subcommand on the existing `graph_group`.

Exit codes encode the verdict so the Plan D supervisor can consume them directly, and so the fail-closed rule is enforced by the process contract rather than by prose:

| Exit | Meaning |
|---|---|
| 0 | clean — no pre-existing entity's basis moved |
| 1 | moved — at least one delta |
| 2 | **unwired** — the basis was not computable; explicitly *not* clean |

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_belief_basis_cli.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF

from science_tool.graph.belief import EVIDENCE_LINE_CLASS
from science_tool.graph.cli import graph_group
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.store.identity import graph_uri

CLAIM = URIRef(PROJECT_NS["proposition/p"])
LINE = URIRef(PROJECT_NS["evidence-line/e"])


def _write_graph(path: Path, *, with_line: bool) -> None:
    dataset = Dataset()
    knowledge = dataset.graph(graph_uri("graph/knowledge"))
    provenance = dataset.graph(graph_uri("graph/provenance"))
    knowledge.add((CLAIM, RDF.type, SCI_NS.Proposition))
    if with_line:
        knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
        knowledge.add((LINE, CITO_NS.supports, CLAIM))
        provenance.add((LINE, SCI_NS.evidenceStrength, Literal("strong")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dataset.serialize(format="trig"))


def test_snapshot_writes_rows_and_digest(tmp_path: Path):
    graph_path = tmp_path / "graph.trig"
    _write_graph(graph_path, with_line=True)
    out = tmp_path / "basis.json"
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(out.read_text())
    assert payload["digest"]
    assert any(row["entity_id"] == "proposition:p" for row in payload["rows"])


def test_compare_detects_an_added_evidence_line(tmp_path: Path):
    graph_path = tmp_path / "graph.trig"
    baseline = tmp_path / "before.json"
    _write_graph(graph_path, with_line=False)
    CliRunner().invoke(graph_group, ["belief-basis", "--graph-path", str(graph_path), "--out", str(baseline)])

    _write_graph(graph_path, with_line=True)
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--compare", str(baseline)]
    )
    assert result.exit_code == 1
    assert "proposition:p" in result.output
    assert "units" in result.output


def test_identical_graph_compares_clean(tmp_path: Path):
    graph_path = tmp_path / "graph.trig"
    baseline = tmp_path / "before.json"
    _write_graph(graph_path, with_line=True)
    CliRunner().invoke(graph_group, ["belief-basis", "--graph-path", str(graph_path), "--out", str(baseline)])
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--compare", str(baseline)]
    )
    assert result.exit_code == 0


def test_unwired_graph_exits_two_not_zero(tmp_path: Path):
    """A graph with no typed entities must NOT report clean."""
    graph_path = tmp_path / "graph.trig"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(Dataset().serialize(format="trig"))
    result = CliRunner().invoke(graph_group, ["belief-basis", "--graph-path", str(graph_path)])
    assert result.exit_code == 2
    assert "no_typed_entities" in result.output
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis_cli.py -v`
Expected: FAIL — click reports `No such command 'belief-basis'`, so every test fails on exit code

- [ ] **Step 3: Write the minimal implementation**

Append to `science/src/science_tool/graph/cli.py`. No new top-level imports are needed: the module already imports `Path` (line 5), `click` (line 7), and `DEFAULT_GRAPH_PATH` from `science_tool.graph.store`, and defines `graph_group` at line 42. Use `DEFAULT_GRAPH_PATH` rather than a literal path — a second spelling of the default would drift.

```python
@graph_group.command("belief-basis")
@click.option(
    "--graph-path",
    type=click.Path(path_type=Path),
    default=DEFAULT_GRAPH_PATH,
    show_default=True,
    help="Materialized graph to read.",
)
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=None, help="Write the capture to this path as JSON.")
@click.option("--compare", "compare_path", type=click.Path(path_type=Path), default=None, help="Compare the current basis against a previous capture.")
def belief_basis_command(graph_path: Path, out_path: Path | None, compare_path: Path | None) -> None:
    """Capture or compare the per-entity belief basis.

    Exit codes: 0 clean, 1 a pre-existing entity's basis moved, 2 unwired
    (not computable — explicitly NOT clean).
    """
    import json
    import sys

    from science_tool.graph.belief_basis import EntityBasis, basis_digest, capture_basis, compare_bases
    from science_tool.graph.store.identity import graph_uri
    from science_tool.graph.trig import load_trig_dataset_preserving_literals

    dataset = load_trig_dataset_preserving_literals(graph_path)
    result = capture_basis(
        dataset.graph(graph_uri("graph/knowledge")),
        dataset.graph(graph_uri("graph/provenance")),
    )
    if result.status == "unwired":
        click.echo(f"unwired ({result.code}): {result.reason}")
        sys.exit(2)

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {"digest": basis_digest(result.rows), "rows": [r.model_dump(mode="json") for r in result.rows]},
                indent=2,
            )
        )
        click.echo(f"captured {len(result.rows)} entities -> {out_path}")

    if compare_path is None:
        sys.exit(0)

    previous = json.loads(compare_path.read_text())
    deltas = compare_bases([EntityBasis(**row) for row in previous["rows"]], result.rows)
    if not deltas:
        click.echo("clean: no pre-existing entity's belief basis moved")
        sys.exit(0)
    for delta in deltas:
        click.echo(f"MOVED {delta.entity_id}: {','.join(delta.changed)} — {delta.detail}")
    sys.exit(1)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis_cli.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full check suite**

```bash
cd science && uv run --frozen pytest tests/test_belief_basis.py tests/test_belief_basis_cli.py -v
cd science && uv run ruff check
cd science && uv run pyright
```
Expected: all pass, no new ruff or pyright findings.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/cli.py science/tests/test_belief_basis_cli.py
git commit -m "feat(graph): add belief-basis capture/compare command with fail-closed exit codes"
```

---

## Deferred to later plans

These are spec requirements this plan deliberately does **not** cover. They are recorded so a spec-coverage review can see they were chosen, not missed.

- **Additional scalar comparison** where `belief_scalar_enabled()` is true (spec §5) — Plan D, with the supervisor, which is the first component holding a project root.
- **Run record**, `base_commit`, `basis_digest` persistence (spec §2) — Plan B.
- **`run_ref` entity field** (spec §3) — Plan B.
- **Default-deny path gate** and the **one-way perturbation alarm** (spec §4, §5 layers 1 and 3) — Plan C.
- **Supervisor lifecycle**, commit-mark verification, quarantine, `science feedback` filing, `science validate` wiring (spec §0, §6) — Plan D.
