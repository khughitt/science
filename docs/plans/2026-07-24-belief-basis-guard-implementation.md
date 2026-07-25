# Belief-Basis Guard Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the observable the autonomy envelope's semantic gate is defined over — capture a per-entity *belief basis* from a materialized graph, seal it in a verifiable snapshot, and compare two snapshots into a typed delta.

**Architecture:** One new pure module, `graph/belief_basis.py`, plus one CLI subcommand. Capture takes two `rdflib.Graph` objects (knowledge, provenance) rather than a `Dataset`, matching how `collect_evidence_units` is already tested, so every function is unit-testable without building a project. Basis capture reuses the exact per-entity recipe already used by the attention instrument (`graph/attention.py:350-353`): expand the target closure, collect evidence units, record policy identity. It deliberately does **not** call `aggregate_belief` — the whole point is to compare inputs, not the aggregated verdict.

**Tech Stack:** Python 3.12+, pydantic v2, rdflib, click, pytest. Package root is `science/` (`science/pyproject.toml`); there is no root `pyproject.toml`.

## Global Constraints

- The basis is **target closure + raw evidence-unit multiset + policy identity**. Never merely the final ordinal magnitude — a run whose units change but cancel must be detectable.
- An uncomputable basis yields exit code 2 / `InstrumentResult.unwired`. **`unwired` never means clean.** Every input that cannot be read, parsed, or verified is uncomputable — not a belief movement.
- `belief_scalar` / `belief_scalar_enabled` must NOT be consulted anywhere in this plan. It is opt-in and returns `False` when unconfigured, so a gate defined over it fails open. It is an *additional* comparison only, and lands in Plan D.
- Serialization must **fail closed**: no `default=` fallback in `json.dumps`, and `extra="forbid"` on every persisted model, so an unrepresentable or unrecognized field raises rather than being silently coerced or dropped.
- All commands run from `science/`: `cd science && uv run --frozen pytest`, `uv run ruff check`, `uv run pyright`.
- Pyright is configured once by the repo-root `pyrightconfig.json`; do not add a `[tool.pyright]` block.
- Conventional commits. **No AI-attribution trailer or footer on any commit.**
- Composition over inheritance; explicit over defensive; fail early rather than silent fallback.

---

## File Structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/graph/belief_basis.py` | **Create.** Unit keying, basis capture, digest, snapshot envelope, comparison. Pure — no filesystem, no project config. |
| `science/src/science_tool/graph/cli.py` | **Modify.** Add the `belief-basis` subcommand to the existing `graph_group`. |
| `science/tests/test_belief_basis.py` | **Create.** Unit tests for keying, capture, digest, snapshot, comparison. |
| `science/tests/test_belief_basis_cli.py` | **Create.** CLI tests: mode exclusivity, snapshot round-trip, and the three exit codes. |

`belief_basis.py` sits beside `belief.py`, `belief_policy.py`, and `belief_scalar.py` because it changes when belief changes — that is the coupling that matters.

---

### Task 1: Canonical evidence-unit key

**Files:**
- Create: `science/src/science_tool/graph/belief_basis.py`
- Test: `science/tests/test_belief_basis.py`

**Interfaces:**
- Consumes: `EvidenceUnit` from `science_tool.graph.belief` — a `@dataclass(frozen=True)` with **18 fields** spanning `graph/belief.py:20-48`. Do not assume you have seen them all by reading the first screenful; the last five (`target_polarity`, `quant_beta`, `quant_prob_sign`, `confidence`, `qa_failed_datasets`) are appended below a comment block.
- Produces: `unit_key(unit: EvidenceUnit) -> str`.

The key is built from `dataclasses.asdict` rather than a hand-listed field subset. This is the load-bearing property: when someone adds a new field to `EvidenceUnit`, it enters the key automatically, so an unrecognized belief input changes the basis instead of being silently omitted from it. A hand-listed subset would fail open on exactly the change most likely to matter.

`json.dumps` is called **without** a `default=` fallback. A `default=str` would silently accept a future non-JSON-native field type and could collapse two distinct values into the same string. Without it, such a field raises `TypeError` at capture time — which is the correct, visible failure.

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


def _distinct(value: object) -> object:
    """Return a value of compatible shape that differs from `value`."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, float):
        return value + 1.0
    if isinstance(value, tuple):
        return (*value, "perturbed")
    if isinstance(value, str):
        return value + "-perturbed"
    return "perturbed"  # None, and anything else


def test_identical_units_share_a_key():
    assert unit_key(_u()) == unit_key(_u())


def test_differing_strength_changes_the_key():
    assert unit_key(_u(strength="strong")) != unit_key(_u(strength="weak"))


def test_every_field_value_affects_the_key():
    """Fail-closed: every field's VALUE must reach the key, not just its name.

    Checking that field names appear in the key would pass an implementation
    serializing {name: None} for every field. Perturbing each value in turn
    catches that, and stays valid if unit_key later returns a hash instead
    of a JSON string.
    """
    base = _u()
    for field in dataclasses.fields(EvidenceUnit):
        mutated = dataclasses.replace(base, **{field.name: _distinct(getattr(base, field.name))})
        assert unit_key(mutated) != unit_key(base), f"{field.name} does not affect the key"


def test_unserializable_value_raises_rather_than_coercing():
    """No `default=` fallback: an unrepresentable value must fail loudly at capture.

    A `default=str` would stringify this and could collapse two distinct objects
    into one key, silently weakening the basis.
    """
    import pytest

    unit = dataclasses.replace(_u(), source=object())
    with pytest.raises(TypeError):
        unit_key(unit)
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

    No `default=` fallback: a future field whose type is not JSON-native must raise
    here rather than be coerced to a string, which could collapse distinct values.
    """
    return json.dumps(asdict(unit), sort_keys=True)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis.py -v`
Expected: PASS (4 tests)

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
- Consumes: `unit_key` (Task 1); `collect_evidence_units(knowledge, provenance, targets)` (`graph/belief.py:123`); `_evidence_targets_for_uri(knowledge, target_uri)` and `canonical_id_from_entity_uri(uri)` — both imported from `science_tool.graph.store`, the same path `graph/attention.py:22` uses; `DEFAULT_BELIEF_POLICY` (`graph/belief_policy.py:98`); `InstrumentResult` (`science_tool/instruments.py:74`).
- Produces: `class EntityBasis` (frozen, `extra="forbid"` pydantic model with fields `entity_id: str`, `uri: str`, `target_uris: tuple[str, ...]`, `unit_keys: tuple[str, ...]`, `policy_id: str`, `policy_version: str`); `capture_basis(knowledge, provenance, *, policy=DEFAULT_BELIEF_POLICY) -> InstrumentResult[EntityBasis]`; the constant `NO_TYPED_ENTITIES = "no_typed_entities"`.

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
from science_tool.instruments import InstrumentResult

# `_evidence_targets_for_uri` is private to the store package but has no public
# equivalent; the attention instrument imports it by this same path
# (graph/attention.py:22). Do NOT "fix" this to a public path — none exists, and
# the basis must expand targets exactly as attention does or the two disagree
# about what an entity's evidence is.
from science_tool.graph.store import _evidence_targets_for_uri, canonical_id_from_entity_uri

#: The sole precondition of basis capture. With no typed project entity in
#: graph/knowledge, NO entity has been assessed and the basis is not a basis.
NO_TYPED_ENTITIES = "no_typed_entities"


class EntityBasis(BaseModel):
    """The belief inputs for one entity, in comparable canonical form."""

    model_config = ConfigDict(frozen=True, extra="forbid")

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
Expected: PASS (8 tests)

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


def test_empty_capture_has_its_own_digest():
    """The empty basis must be distinguishable, not merely reproducible."""
    assert basis_digest([]) != basis_digest([_basis("proposition:a")])
```

> **Corrected during execution.** This test was originally drafted as
> `assert basis_digest([]) == basis_digest([])`, which is true for any
> implementation — including one that ignores its argument entirely. A test whose
> assertion cannot distinguish a correct implementation from a stub is decoration.
> Every assertion in a plan's test code has to be able to fail.

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

    Persisted in the snapshot envelope and in the run record so a later
    validation can prove it compared against the same starting state.
    """
    Ordered by the serialized row itself, not by (uri, entity_id): that pair is not
    unique by construction, and two rows sharing it would otherwise fall back to
    input order, leaving a known input-order dependence in the observable this
    whole module exists to make reproducible.
    """
    rows = sorted(json.dumps(b.model_dump(mode="json"), sort_keys=True) for b in bases)
    return hashlib.sha256(json.dumps(rows).encode("utf-8")).hexdigest()
```

> **Corrected during execution.** The sort key was drafted as `b.uri` alone. Any
> key that is not unique leaves ties broken by input order, so the "order-independent"
> claim in the docstring would have been false for rows sharing it. Sort by the
> serialized row and the order is total by construction.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief_basis.py science/tests/test_belief_basis.py
git commit -m "feat(graph): add order-independent belief-basis digest"
```

---

### Task 4: Verified snapshot envelope

**Files:**
- Modify: `science/src/science_tool/graph/belief_basis.py`
- Test: `science/tests/test_belief_basis.py`

**Interfaces:**
- Consumes: `EntityBasis` (Task 2), `basis_digest` (Task 3).
- Produces: `BASIS_SNAPSHOT_SCHEMA_VERSION: int`; `class BasisSnapshot` (frozen, `extra="forbid"`, fields `schema_version: int`, `digest: str`, `rows: tuple[EntityBasis, ...]`); `class SnapshotIntegrityError(ValueError)`; `build_snapshot(rows: Iterable[EntityBasis]) -> BasisSnapshot`; `load_snapshot(payload: object) -> BasisSnapshot`.

A digest that is written but never checked is decoration. `load_snapshot` recomputes the digest from the rows and refuses to return a snapshot whose stored digest disagrees, so a baseline that was **corrupted or altered without being resealed** cannot yield a clean comparison — it raises, and the CLI turns that into `unwired`.

Be precise about what this does not do: a wholly substituted snapshot whose digest was *recomputed* over the substituted rows is internally consistent and passes. That is integrity, not authenticity, and closing it is out of scope for Plan A — authenticity comes from comparing against the supervisor-attested digest in the run record (Plan B/D), which the actor cannot write.

`load_snapshot` takes `object`, not `dict`, and goes through `model_validate`. Wrong-shaped JSON — a top-level array, a string, `null` — must surface as a caught `ValidationError` (which subclasses `ValueError`) rather than a `TypeError` escaping from `**payload` unpacking, which the CLI's handler would miss and report as a belief movement.

`extra="forbid"` plus an explicit `schema_version` closes the other direction: a *newer* snapshot carrying basis fields this code does not know about must fail loudly rather than be silently truncated into a comparison that then reports clean. Plan D additionally compares this digest against the supervisor-attested digest in the run record; Plan A only guarantees internal consistency.

- [ ] **Step 1: Write the failing tests**

```python
# append to science/tests/test_belief_basis.py
import pytest
from pydantic import ValidationError

from science_tool.graph.belief_basis import (
    BASIS_SNAPSHOT_SCHEMA_VERSION,
    SnapshotIntegrityError,
    build_snapshot,
    load_snapshot,
)


def test_snapshot_round_trips():
    snapshot = build_snapshot([_basis("proposition:a", ("k1",))])
    reloaded = load_snapshot(snapshot.model_dump(mode="json"))
    assert reloaded.rows == snapshot.rows
    assert reloaded.digest == snapshot.digest


def test_tampered_rows_are_rejected():
    """A substituted baseline must not be able to produce a clean comparison."""
    payload = build_snapshot([_basis("proposition:a", ("k1",))]).model_dump(mode="json")
    payload["rows"][0]["unit_keys"] = ["k2"]
    with pytest.raises(SnapshotIntegrityError, match="digest mismatch"):
        load_snapshot(payload)


def test_unknown_schema_version_is_rejected():
    payload = build_snapshot([_basis("proposition:a")]).model_dump(mode="json")
    payload["schema_version"] = BASIS_SNAPSHOT_SCHEMA_VERSION + 1
    with pytest.raises(SnapshotIntegrityError, match="schema_version"):
        load_snapshot(payload)


def test_unknown_basis_field_is_rejected_not_dropped():
    """A newer snapshot must fail loudly rather than be truncated into a clean compare."""
    payload = build_snapshot([_basis("proposition:a")]).model_dump(mode="json")
    payload["rows"][0]["future_field"] = "value"
    with pytest.raises(ValidationError):  # extra="forbid"
        load_snapshot(payload)


@pytest.mark.parametrize("payload", [[], "snapshot", None, 42])
def test_wrong_shaped_payload_raises_validation_error(payload: object):
    """A top-level array or scalar must raise ValidationError, not TypeError.

    A TypeError from `**payload` unpacking would escape the CLI's handler and be
    reported as exit 1 — a belief movement — instead of unwired.
    """
    with pytest.raises(ValidationError):
        load_snapshot(payload)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis.py -k snapshot -v`
Expected: FAIL — `ImportError: cannot import name 'BASIS_SNAPSHOT_SCHEMA_VERSION'`

- [ ] **Step 3: Write the minimal implementation**

```python
# add to science/src/science_tool/graph/belief_basis.py

#: Bump when the shape of EntityBasis or the snapshot envelope changes.
BASIS_SNAPSHOT_SCHEMA_VERSION = 1


class SnapshotIntegrityError(ValueError):
    """A snapshot could not be trusted: bad digest, or a schema version this code cannot read."""


class BasisSnapshot(BaseModel):
    """A sealed capture. The digest is verified on load, never merely carried."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int
    digest: str
    rows: tuple[EntityBasis, ...]


def build_snapshot(rows: Iterable[EntityBasis]) -> BasisSnapshot:
    sealed = tuple(rows)
    return BasisSnapshot(
        schema_version=BASIS_SNAPSHOT_SCHEMA_VERSION,
        digest=basis_digest(sealed),
        rows=sealed,
    )


def load_snapshot(payload: object) -> BasisSnapshot:
    """Parse and VERIFY a snapshot. Raises rather than returning something untrustworthy.

    Takes `object` and validates: a top-level array or scalar must raise
    pydantic's ValidationError (a ValueError), not a TypeError from `**` unpacking
    that the CLI handler would let through as a belief movement.
    """
    snapshot = BasisSnapshot.model_validate(payload)
    if snapshot.schema_version != BASIS_SNAPSHOT_SCHEMA_VERSION:
        raise SnapshotIntegrityError(
            f"snapshot schema_version {snapshot.schema_version} != {BASIS_SNAPSHOT_SCHEMA_VERSION}; "
            "this snapshot was written by a different version of the basis format"
        )
    recomputed = basis_digest(snapshot.rows)
    if recomputed != snapshot.digest:
        raise SnapshotIntegrityError(f"snapshot digest mismatch: stored {snapshot.digest}, recomputed {recomputed}")
    return snapshot
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis.py -v`
Expected: PASS (19 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief_basis.py science/tests/test_belief_basis.py
git commit -m "feat(graph): seal belief-basis captures in a digest-verified snapshot"
```

---

### Task 5: Basis comparison

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
Expected: PASS (24 tests)

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief_basis.py science/tests/test_belief_basis.py
git commit -m "feat(graph): compare belief bases into typed per-entity deltas"
```

---

### Task 6: `science graph belief-basis` command

**Files:**
- Modify: `science/src/science_tool/graph/cli.py`
- Test: `science/tests/test_belief_basis_cli.py`

**Interfaces:**
- Consumes: `capture_basis`, `build_snapshot`, `load_snapshot`, `compare_bases`, `SnapshotIntegrityError` (Tasks 2-5); `load_trig_dataset_preserving_literals(graph_path)` (`graph/trig.py`, used the same way at `wander/sampling.py:37`); `graph_uri(layer)` (`graph/store/identity.py:63`).
- Produces: a `belief-basis` subcommand on the existing `graph_group`.

Exit codes encode the verdict so the Plan D supervisor can consume them directly, and so the fail-closed rule is enforced by the process contract rather than by prose:

| Exit | Meaning |
|---|---|
| 0 | clean — no pre-existing entity's basis moved |
| 1 | moved — at least one delta |
| 2 | **unwired** — the basis was not computable; explicitly *not* clean |

Two rules make the table true rather than aspirational:

1. **`--out` and `--compare` are mutually exclusive, and exactly one is required.** Allowing both would let a caller pass the same path for each, overwriting the baseline with the current capture and then reporting clean — a guard that erases its own evidence. The supervisor never needs both: it captures with `--out` at run start and compares with `--compare` at run end.
2. **Every unreadable input is exit 2, not exit 1.** A missing or malformed TriG, unparseable snapshot JSON, a failed digest check, and a schema-version mismatch are all *uncomputable*, and an uncaught exception would surface as exit code 1 — which the table defines as a genuine belief movement. They are caught at the CLI boundary and reported as `unwired`.

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


def _snapshot(graph_path: Path, out: Path) -> None:
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--out", str(out)]
    )
    assert result.exit_code == 0, result.output


def test_snapshot_writes_verified_rows(tmp_path: Path):
    graph_path, out = tmp_path / "graph.trig", tmp_path / "basis.json"
    _write_graph(graph_path, with_line=True)
    _snapshot(graph_path, out)
    payload = json.loads(out.read_text())
    assert payload["digest"] and payload["schema_version"] == 1
    assert any(row["entity_id"] == "proposition:p" for row in payload["rows"])


def test_out_and_compare_are_mutually_exclusive(tmp_path: Path):
    """Passing the same path for both would overwrite the baseline and report clean."""
    graph_path, out = tmp_path / "graph.trig", tmp_path / "basis.json"
    _write_graph(graph_path, with_line=True)
    _snapshot(graph_path, out)
    result = CliRunner().invoke(
        graph_group,
        ["belief-basis", "--graph-path", str(graph_path), "--out", str(out), "--compare", str(out)],
    )
    assert result.exit_code == 2
    assert "mutually exclusive" in result.output


def test_compare_detects_an_added_evidence_line(tmp_path: Path):
    graph_path, baseline = tmp_path / "graph.trig", tmp_path / "before.json"
    _write_graph(graph_path, with_line=False)
    _snapshot(graph_path, baseline)

    _write_graph(graph_path, with_line=True)
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--compare", str(baseline)]
    )
    assert result.exit_code == 1
    assert "proposition:p" in result.output and "units" in result.output


def test_identical_graph_compares_clean(tmp_path: Path):
    graph_path, baseline = tmp_path / "graph.trig", tmp_path / "before.json"
    _write_graph(graph_path, with_line=True)
    _snapshot(graph_path, baseline)
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--compare", str(baseline)]
    )
    assert result.exit_code == 0


def test_unwired_graph_exits_two_not_zero(tmp_path: Path):
    """A graph with no typed entities must NOT report clean."""
    graph_path = tmp_path / "graph.trig"
    graph_path.write_text(Dataset().serialize(format="trig"))
    result = CliRunner().invoke(graph_group, ["belief-basis", "--graph-path", str(graph_path), "--out", str(tmp_path / "o.json")])
    assert result.exit_code == 2
    assert "no_typed_entities" in result.output


def test_missing_graph_is_unwired_not_moved(tmp_path: Path):
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(tmp_path / "absent.trig"), "--out", str(tmp_path / "o.json")]
    )
    assert result.exit_code == 2


def test_tampered_baseline_is_unwired_not_clean(tmp_path: Path):
    """A corrupted baseline must never yield a clean comparison."""
    graph_path, baseline = tmp_path / "graph.trig", tmp_path / "before.json"
    _write_graph(graph_path, with_line=True)
    _snapshot(graph_path, baseline)
    payload = json.loads(baseline.read_text())
    # Target by entity_id, not position: rows are sorted by URI, and
    # "evidence-line:e" sorts before "proposition:p" and already has empty
    # unit_keys, so a positional rows[0] edit is a no-op that leaves the
    # digest unchanged and the baseline still (correctly) trusted.
    row = next(r for r in payload["rows"] if r["entity_id"] == "proposition:p")
    row["unit_keys"] = []
    baseline.write_text(json.dumps(payload))
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--compare", str(baseline)]
    )
    assert result.exit_code == 2
    assert "digest mismatch" in result.output
```

> **Corrected during execution.** The tamper above was drafted as
> `payload["rows"][0]["unit_keys"] = []`, which is a no-op: `capture_basis` sorts
> rows by full URI, so row 0 is `evidence-line:e`, whose `unit_keys` is already
> empty. The digest still matched, the baseline was still trusted, and the test
> failed on `assert 0 == 2`. Select the row you mean to corrupt by identity, never
> by position in a sorted list.
>
> A related lesson from the same review: the exit-2 assertions in this section are
> **not** sufficient on their own. Click returns exit 2 for its own usage errors,
> so `assert result.exit_code == 2` still passes if the command is removed from the
> group or an option renamed. Every exit-2 test also needs `assert "unwired:" in
> result.output`, as the shipped tests do.

```python
def test_malformed_baseline_json_is_unwired(tmp_path: Path):
    graph_path, baseline = tmp_path / "graph.trig", tmp_path / "before.json"
    _write_graph(graph_path, with_line=True)
    baseline.write_text("{not json")
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--compare", str(baseline)]
    )
    assert result.exit_code == 2


def test_json_array_baseline_is_unwired_not_moved(tmp_path: Path):
    """Valid JSON of the wrong shape must not escape as exit 1.

    `BasisSnapshot(**payload)` on a list raises TypeError, which the handler would
    miss; load_snapshot uses model_validate so this is a caught ValidationError.
    """
    graph_path, baseline = tmp_path / "graph.trig", tmp_path / "before.json"
    _write_graph(graph_path, with_line=True)
    baseline.write_text("[]")
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--compare", str(baseline)]
    )
    assert result.exit_code == 2


def test_capture_serialization_failure_is_unwired(tmp_path: Path, monkeypatch):
    """A basis that cannot be serialized is uncomputable, not a belief movement.

    unit_key raises TypeError by design on a non-JSON-native field value; that
    must reach exit 2 rather than escaping as exit 1.
    """
    def _boom(*_args, **_kwargs):
        raise TypeError("Object of type object is not JSON serializable")

    monkeypatch.setattr("science_tool.graph.belief_basis.capture_basis", _boom)
    graph_path = tmp_path / "graph.trig"
    _write_graph(graph_path, with_line=True)
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--out", str(tmp_path / "o.json")]
    )
    assert result.exit_code == 2
    assert "could not compute basis" in result.output
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
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=None, help="Write a sealed capture to this path.")
@click.option("--compare", "compare_path", type=click.Path(path_type=Path), default=None, help="Compare the current basis against a previous capture.")
def belief_basis_command(graph_path: Path, out_path: Path | None, compare_path: Path | None) -> None:
    """Capture or compare the per-entity belief basis.

    Exactly one of --out / --compare. Exit codes: 0 clean, 1 a pre-existing
    entity's basis moved, 2 unwired (not computable — explicitly NOT clean).
    """
    import json
    import sys
    from typing import NoReturn

    from science_tool.graph.belief_basis import (
        build_snapshot,
        capture_basis,
        compare_bases,
        load_snapshot,
    )
    from science_tool.graph.store.identity import graph_uri
    from science_tool.graph.trig import load_trig_dataset_preserving_literals

    def _unwired(message: str) -> NoReturn:
        """Exit 2. Typed NoReturn so the checker knows nothing after a call is reachable."""
        click.echo(f"unwired: {message}")
        sys.exit(2)

    # A caller passing the same path for both would overwrite the baseline with the
    # current capture and then compare it against itself — always clean.
    if (out_path is None) == (compare_path is None):
        _unwired("--out and --compare are mutually exclusive; pass exactly one")

    try:
        dataset = load_trig_dataset_preserving_literals(graph_path)
        result = capture_basis(
            dataset.graph(graph_uri("graph/knowledge")),
            dataset.graph(graph_uri("graph/provenance")),
        )
    except Exception as exc:
        # Two distinct uncomputable cases share this handler: an unreadable or
        # malformed graph, and a basis that cannot be serialized (a future
        # EvidenceUnit field with a non-JSON-native type raises TypeError in
        # unit_key by design). Neither is a belief movement.
        _unwired(f"could not compute basis from {graph_path}: {exc}")

    if result.status == "unwired":
        _unwired(f"({result.code}) {result.reason}")

    if out_path is not None:
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(build_snapshot(result.rows).model_dump_json(indent=2))
        except Exception as exc:  # unwritable output is uncomputable, not clean
            _unwired(f"could not write capture to {out_path}: {exc}")
        click.echo(f"captured {len(result.rows)} entities -> {out_path}")
        sys.exit(0)

    assert compare_path is not None  # exactly-one check above
    try:
        previous = load_snapshot(json.loads(compare_path.read_text()))
    except Exception as exc:
        # OSError, JSONDecodeError, ValidationError, SnapshotIntegrityError — a
        # baseline we cannot read or cannot trust is unwired, never clean.
        _unwired(f"could not trust baseline {compare_path}: {exc}")

    deltas = compare_bases(previous.rows, result.rows)
    if not deltas:
        click.echo("clean: no pre-existing entity's belief basis moved")
        sys.exit(0)
    for delta in deltas:
        click.echo(f"MOVED {delta.entity_id}: {','.join(delta.changed)} — {delta.detail}")
    sys.exit(1)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_belief_basis_cli.py -v`
Expected: PASS (10 tests)

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
- **Run record**, `base_commit`, and comparison of the snapshot digest against the supervisor-attested digest (spec §2) — Plan B/D. Plan A guarantees a snapshot is internally consistent; only the run record can say it is the *right* snapshot.
- **`run_ref` entity field** (spec §3) — Plan B.
- **Default-deny path gate** and the **one-way perturbation alarm** (spec §4, §5 layers 1 and 3) — Plan C.
- **Supervisor lifecycle**, commit-mark verification, quarantine, `science feedback` filing, `science validate` wiring (spec §0, §6) — Plan D.
