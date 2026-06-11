# Bundle Belief Roll-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive a `hypothesis`/`mechanism` bundle's belief from its member propositions under an explicit, authored composition rule (v1 = weakest-link).

**Architecture:** One bundle-belief engine (`graph/bundle_belief.py`) computes each member's existing per-proposition belief, then rolls up by weakest-link (min) in continuous space — independence-safe by construction. Refutation propagates as a separate boolean axis, never a fake ordinal. `composition_rule` is a real validated model field on the common `Entity` base, materialized as `sci:compositionRule`; reserved rules hard-error. The existing hypothesis evidence-union path stays a *coverage* signal, no longer the bundle's belief.

**Tech Stack:** Python 3.12, pydantic v2 (`science_model`), rdflib/TriG (`science_tool.graph`), pytest, uv, ruff.

**Design doc:** `docs/plans/2026-06-11-bundle-belief-rollup-design.md` (read it; this plan implements it).

**Test command (this repo):** `uv run --frozen pytest <path> -m "not snapshot and not real_projects"`. Full check: `uv run --frozen pytest science/tests -m "not snapshot and not real_projects"` then `uv run --frozen ruff check science`.

---

## File Structure

- `science/model/src/science_model/reasoning.py` — add `CompositionRule` StrEnum + `RESERVED_COMPOSITION_RULES`, `WEAKEST_LINK_COMPOSITION_RULES` frozensets (sits beside the existing `Predicate`/`Polarity` enums).
- `science/model/src/science_model/entities.py` — add `composition_rule: CompositionRule | None` to the `Entity` base (line 220) + a reserved-value model validator. `MechanismEntity` (490s) and bare `hypothesis` (parses to plain `Entity`) both inherit it.
- `science/model/src/science_model/__init__.py` — export `CompositionRule`.
- `science/src/science_tool/graph/materialize.py` — emit `sci:compositionRule` inside `_add_reasoning_metadata` (≈line 1033).
- `science/src/science_tool/graph/bundle_belief.py` — **NEW.** Member enumeration, `MemberBelief`, `BundleBeliefResult`, `roll_up_weakest_link`, `belief_for_entity` dispatch, `UnresolvedBundleError`.
- `science/src/science_tool/graph/belief_snapshot.py` — emit bundle rows (hypothesis + mechanism) via the engine; stop using the coverage-union as the bundle's belief.
- Tests: `science/tests/test_composition_rule_field.py`, `test_composition_rule_materialize.py`, `test_bundle_members.py`, `test_bundle_belief_rollup.py`, `test_bundle_belief_snapshot.py`.

---

## Phase 1 — composition_rule model field, materialization, member enumeration

### Task 1: `CompositionRule` enum + `Entity.composition_rule` field + reserved-value validator

**Files:**
- Modify: `science/model/src/science_model/reasoning.py`
- Modify: `science/model/src/science_model/entities.py:220` (the `Entity` base class)
- Modify: `science/model/src/science_model/__init__.py`
- Test: `science/tests/test_composition_rule_field.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_composition_rule_field.py
from __future__ import annotations

import pytest

from science_model.entities import Entity, EntityType
from science_model.reasoning import CompositionRule, RESERVED_COMPOSITION_RULES, WEAKEST_LINK_COMPOSITION_RULES


def _entity(**kw):
    # type MUST match core_entity_type_for_kind(kind) — Entity._validate_kind_type_consistency
    # (entities.py:343) rejects a mismatch, so direct construction requires an explicit type=.
    base = dict(
        id="hypothesis:h1", kind="hypothesis", type=EntityType.HYPOTHESIS, title="H1", project="p",
        ontology_terms=[], related=[], source_refs=[], content_preview="",
        file_path="x.md",
    )
    base.update(kw)
    return Entity(**base)


def test_default_is_none():
    assert _entity().composition_rule is None


def test_accepts_weakest_link_rules():
    for rule in ("all_steps", "conjunctive"):
        assert _entity(composition_rule=rule).composition_rule == CompositionRule(rule)


@pytest.mark.parametrize("rule", ["evidence_union", "faceted_support"])
def test_reserved_rules_rejected_at_model_layer(rule):
    with pytest.raises(ValueError, match="reserved"):
        _entity(composition_rule=rule)


def test_composition_rule_rejected_on_non_bundle_kind():
    with pytest.raises(ValueError, match="bundle kinds"):
        _entity(id="proposition:p1", kind="proposition", type=EntityType.PROPOSITION, composition_rule="conjunctive")


def test_enum_partitions_are_disjoint_and_complete():
    assert RESERVED_COMPOSITION_RULES.isdisjoint(WEAKEST_LINK_COMPOSITION_RULES)
    assert RESERVED_COMPOSITION_RULES | WEAKEST_LINK_COMPOSITION_RULES == set(CompositionRule)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_composition_rule_field.py -v`
Expected: FAIL — `ImportError: cannot import name 'CompositionRule'`.

- [ ] **Step 3: Add the enum to `reasoning.py`**

Append near the existing `Predicate`/`Polarity` enums:

```python
class CompositionRule(StrEnum):
    """How a bundle (hypothesis/mechanism) composes its member propositions.

    `all_steps`/`conjunctive` share the v1 weakest-link implementation but keep
    distinct names to preserve authored intent. `evidence_union`/`faceted_support`
    are RESERVED — declared so the names are stable, but not implemented in v1
    (see docs/plans/2026-06-11-bundle-belief-rollup-design.md §4).
    """

    ALL_STEPS = "all_steps"            # mechanism default — every step must hold
    CONJUNCTIVE = "conjunctive"        # hypothesis default — sub-claims jointly assert the conjecture
    EVIDENCE_UNION = "evidence_union"  # RESERVED
    FACETED_SUPPORT = "faceted_support"  # RESERVED


RESERVED_COMPOSITION_RULES = frozenset({CompositionRule.EVIDENCE_UNION, CompositionRule.FACETED_SUPPORT})
WEAKEST_LINK_COMPOSITION_RULES = frozenset({CompositionRule.ALL_STEPS, CompositionRule.CONJUNCTIVE})
```

(If `StrEnum` is not already imported in `reasoning.py`, it is — `Predicate`/`Polarity` use it.)

- [ ] **Step 4: Add the field + validator to `Entity`**

In `entities.py`, add the import near the other `reasoning` imports:

```python
from science_model.reasoning import CompositionRule, RESERVED_COMPOSITION_RULES
```

Add the field to the `Entity` class body (with the other optional type-specific fields, after `review_state`):

```python
    composition_rule: CompositionRule | None = None
```

Add a validator method on `Entity` (mirroring the existing `@model_validator(mode="after")` methods):

```python
    @model_validator(mode="after")
    def _validate_composition_rule(self) -> "Entity":
        if self.composition_rule is None:
            return self
        if self.kind not in ("hypothesis", "mechanism"):
            raise ValueError(
                f"composition_rule is only meaningful on bundle kinds (hypothesis/mechanism), "
                f"not {self.kind!r}; remove it."
            )
        if self.composition_rule in RESERVED_COMPOSITION_RULES:
            raise ValueError(
                f"composition_rule {self.composition_rule.value!r} is reserved and not "
                "implemented in v1 (see docs/plans/2026-06-11-bundle-belief-rollup-design.md "
                "§4); use 'all_steps' or 'conjunctive'."
            )
        return self
```

- [ ] **Step 5: Export from `__init__.py`**

Add `CompositionRule` to the imports from `.reasoning` and to `__all__` in `science/model/src/science_model/__init__.py` (follow the existing `Predicate`/`Polarity` export pattern).

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run --frozen pytest science/tests/test_composition_rule_field.py -v`
Expected: PASS (4 tests / parametrized cases green).

- [ ] **Step 7: Commit**

```bash
git add science/model/src/science_model/reasoning.py science/model/src/science_model/entities.py science/model/src/science_model/__init__.py science/tests/test_composition_rule_field.py
git commit -m "feat(model): composition_rule field on Entity; reserved rules rejected at model layer"
```

---

### Task 2: Materialize `sci:compositionRule`

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (`_add_reasoning_metadata`, ≈line 1033)
- Test: `science/tests/test_composition_rule_materialize.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_composition_rule_materialize.py
from __future__ import annotations

from rdflib import Literal, URIRef

from science_model.entities import Entity, EntityType
from science_tool.graph.io import SCI_NS
from science_tool.graph.materialize import _add_reasoning_metadata
from rdflib import Graph


def _entity(rule):
    # type MUST equal core_entity_type_for_kind("mechanism") — see entities.py:343.
    return Entity(
        id="mechanism:m1", kind="mechanism", type=EntityType.MECHANISM, title="M1", project="p",
        ontology_terms=[], related=[], source_refs=[], content_preview="",
        file_path="x.md", composition_rule=rule,
    )


def test_composition_rule_materialized():
    prov = Graph()
    uri = URIRef("http://example.org/science/entity/mechanism/m1")
    _add_reasoning_metadata(uri=uri, provenance=prov, entity=_entity("all_steps"))
    assert (uri, SCI_NS.compositionRule, Literal("all_steps")) in prov


def test_absent_rule_not_materialized():
    prov = Graph()
    uri = URIRef("http://example.org/science/entity/mechanism/m1")
    _add_reasoning_metadata(uri=uri, provenance=prov, entity=_entity(None))
    assert (uri, SCI_NS.compositionRule, None) not in prov
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_composition_rule_materialize.py -v`
Expected: FAIL — the `compositionRule` triple is absent.

- [ ] **Step 3: Add the materialization line**

Read `_add_reasoning_metadata` (≈line 1033 in `materialize.py`) to match its style — it adds `SCI_NS.claimLayer`, `SCI_NS.identificationStrength`, etc. to `provenance`. Add, alongside those:

```python
    if getattr(entity, "composition_rule", None) is not None:
        provenance.add((uri, SCI_NS.compositionRule, Literal(entity.composition_rule.value)))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest science/tests/test_composition_rule_materialize.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_composition_rule_materialize.py
git commit -m "feat(graph): materialize sci:compositionRule from the model field"
```

---

### Task 3: Member enumeration + composition-rule resolution

**Files:**
- Create: `science/src/science_tool/graph/bundle_belief.py`
- Test: `science/tests/test_bundle_members.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_bundle_members.py
from __future__ import annotations

from rdflib import Graph, Literal, RDF, URIRef

from science_model.reasoning import CompositionRule
from science_tool.graph.bundle_belief import bundle_members, bundle_kind, resolve_composition_rule
from science_tool.graph.io import CITO_NS, SCI_NS

HYP = URIRef("http://example.org/science/entity/hypothesis/h1")
MECH = URIRef("http://example.org/science/entity/mechanism/m1")
P1 = URIRef("http://example.org/science/entity/proposition/p1")
P2 = URIRef("http://example.org/science/entity/proposition/p2")
NOTPROP = URIRef("http://example.org/science/entity/observation/o1")


def _props(g, *uris):
    for u in uris:
        g.add((u, RDF.type, SCI_NS.Proposition))


def test_mechanism_members_via_has_proposition():
    k = Graph()
    k.add((MECH, RDF.type, SCI_NS.Mechanism))
    _props(k, P1, P2)
    k.add((MECH, SCI_NS.hasProposition, P1))
    k.add((MECH, SCI_NS.hasProposition, P2))
    assert bundle_members(k, MECH) == [P1, P2]


def test_hypothesis_members_via_reverse_discusses():
    k = Graph()
    k.add((HYP, RDF.type, SCI_NS.Hypothesis))
    _props(k, P1)
    k.add((P1, CITO_NS.discusses, HYP))
    assert bundle_members(k, HYP) == [P1]


def test_union_dedupes_and_ignores_non_propositions():
    k = Graph()
    k.add((HYP, RDF.type, SCI_NS.Hypothesis))
    _props(k, P1)
    k.add((HYP, SCI_NS.hasProposition, P1))
    k.add((P1, CITO_NS.discusses, HYP))         # same member, both directions
    k.add((HYP, SCI_NS.hasProposition, NOTPROP))  # not a Proposition → ignored
    assert bundle_members(k, HYP) == [P1]


def test_non_transitive_does_not_expand_sub_hypotheses():
    k = Graph()
    k.add((HYP, RDF.type, SCI_NS.Hypothesis))
    sub = URIRef("http://example.org/science/entity/hypothesis/h2")
    k.add((sub, RDF.type, SCI_NS.Hypothesis))
    k.add((HYP, SCI_NS.hasProposition, sub))  # a hypothesis, not a Proposition
    assert bundle_members(k, HYP) == []


def test_bundle_kind_and_default_rule():
    k = Graph()
    k.add((HYP, RDF.type, SCI_NS.Hypothesis))
    k.add((MECH, RDF.type, SCI_NS.Mechanism))
    assert bundle_kind(k, HYP) == "hypothesis"
    assert bundle_kind(k, MECH) == "mechanism"
    assert bundle_kind(k, P1) is None
    prov = Graph()
    assert resolve_composition_rule(prov, HYP, "hypothesis") == CompositionRule.CONJUNCTIVE
    assert resolve_composition_rule(prov, MECH, "mechanism") == CompositionRule.ALL_STEPS


def test_authored_rule_overrides_default():
    prov = Graph()
    prov.add((MECH, SCI_NS.compositionRule, Literal("conjunctive")))
    assert resolve_composition_rule(prov, MECH, "mechanism") == CompositionRule.CONJUNCTIVE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_bundle_members.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.graph.bundle_belief`.

- [ ] **Step 3: Create `bundle_belief.py` with the enumeration helpers**

```python
# science/src/science_tool/graph/bundle_belief.py
"""Bundle belief roll-up (design doc 2026-06-11-bundle-belief-rollup-design.md).

A hypothesis/mechanism bundle's belief is derived from its member propositions
under an explicit composition rule. v1 implements weakest-link only.
"""
from __future__ import annotations

from rdflib import RDF, URIRef

from science_model.reasoning import CompositionRule
from .io import CITO_NS, SCI_NS

_BUNDLE_TYPES: dict[str, URIRef] = {
    "hypothesis": SCI_NS.Hypothesis,
    "mechanism": SCI_NS.Mechanism,
}
_KIND_DEFAULT_RULE: dict[str, CompositionRule] = {
    "hypothesis": CompositionRule.CONJUNCTIVE,
    "mechanism": CompositionRule.ALL_STEPS,
}


def bundle_kind(knowledge, uri: URIRef) -> str | None:
    """Return 'hypothesis'/'mechanism' if `uri` is a bundle type, else None."""
    for kind, type_uri in _BUNDLE_TYPES.items():
        if (uri, RDF.type, type_uri) in knowledge:
            return kind
    return None


def bundle_members(knowledge, uri: URIRef) -> list[URIRef]:
    """Direct member propositions: forward sci:hasProposition ∪ reverse cito:discusses.

    Restricted to Proposition-typed targets; non-transitive; deterministic order.
    """
    members: list[URIRef] = []
    seen: set[URIRef] = set()

    def _add(node) -> None:
        if (
            isinstance(node, URIRef)
            and node not in seen
            and (node, RDF.type, SCI_NS.Proposition) in knowledge
        ):
            seen.add(node)
            members.append(node)

    for _, _, obj in knowledge.triples((uri, SCI_NS.hasProposition, None)):
        _add(obj)
    for subj, _, _ in knowledge.triples((None, CITO_NS.discusses, uri)):
        _add(subj)

    members.sort(key=str)
    return members


def resolve_composition_rule(provenance, uri: URIRef, kind: str) -> CompositionRule:
    """Authored sci:compositionRule if present, else the per-kind default."""
    value = provenance.value(uri, SCI_NS.compositionRule)
    if value is not None:
        return CompositionRule(str(value))
    return _KIND_DEFAULT_RULE[kind]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest science/tests/test_bundle_members.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/bundle_belief.py science/tests/test_bundle_members.py
git commit -m "feat(graph): bundle member enumeration + composition-rule resolution"
```

---

## Phase 2 — weakest-link roll-up engine

### Task 4: `MemberBelief`, `BundleBeliefResult`, `roll_up_weakest_link`

**Files:**
- Modify: `science/src/science_tool/graph/bundle_belief.py`
- Test: `science/tests/test_bundle_belief_rollup.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_bundle_belief_rollup.py
from __future__ import annotations

from science_tool.graph.belief import BeliefMagnitude, BeliefResult
from science_tool.graph.bundle_belief import (
    MemberBelief,
    member_rank_key,
    roll_up_weakest_link,
)
from science_model.reasoning import CompositionRule


def _belief(magnitude, *, contested=False, capped=False) -> BeliefResult:
    return BeliefResult(
        magnitude=magnitude, contested=contested, capped_by_refutation=capped,
        support_units=[], dispute_units=[], diagnostics=[],
        contested_groups=set(), excluded=[], flagged_ungrouped=[],
    )


def _member(uri, magnitude, *, contested=False, capped=False) -> MemberBelief:
    b = _belief(magnitude, contested=contested, capped=capped)
    return MemberBelief(
        member_uri=uri, belief=b, scalar=None,
        rank_key=member_rank_key(b, None, uri),
        reason=("speculative: no evidence" if magnitude == BeliefMagnitude.SPECULATIVE else None),
    )


def test_magnitude_is_weakest_member():
    members = [
        _member("p:a", BeliefMagnitude.WELL_SUPPORTED),
        _member("p:b", BeliefMagnitude.FRAGILE),
        _member("p:c", BeliefMagnitude.SUPPORTED),
    ]
    r = roll_up_weakest_link(members, rule=CompositionRule.ALL_STEPS)
    assert r.magnitude == BeliefMagnitude.FRAGILE
    assert r.bottleneck_members == ["p:b"]
    assert r.composition_rule == "all_steps"


def test_refutation_is_separate_axis_not_an_ordinal():
    # A refuted member is FRAGILE (capped); an unestablished member is SPECULATIVE.
    # Magnitude bottoms out at the speculative member; refutation is still flagged.
    members = [
        _member("p:refuted", BeliefMagnitude.FRAGILE, capped=True),
        _member("p:unestablished", BeliefMagnitude.SPECULATIVE),
    ]
    r = roll_up_weakest_link(members, rule=CompositionRule.ALL_STEPS)
    assert r.magnitude == BeliefMagnitude.SPECULATIVE       # unestablished < refuted
    assert r.bottleneck_members == ["p:unestablished"]
    assert r.capped_by_refutation is True                   # refutation still surfaced
    assert r.unresolved_members == ["p:unestablished"]


def test_contested_propagates_if_any_member_contested():
    members = [
        _member("p:a", BeliefMagnitude.SUPPORTED, contested=True),
        _member("p:b", BeliefMagnitude.SUPPORTED),
    ]
    r = roll_up_weakest_link(members, rule=CompositionRule.CONJUNCTIVE)
    assert r.contested is True
    assert r.contested_members == ["p:a"]


def test_rank_key_deterministic_without_scalar():
    # Same ordinal magnitude → tiebreak by member_uri (scalar None → 0.0 component).
    members = [
        _member("p:z", BeliefMagnitude.SUPPORTED),
        _member("p:a", BeliefMagnitude.SUPPORTED),
    ]
    r = roll_up_weakest_link(members, rule=CompositionRule.ALL_STEPS)
    assert [m.member_uri for m in r.member_results] == ["p:a", "p:z"]
    assert set(r.bottleneck_members) == {"p:a", "p:z"}  # both share the min ordinal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_bundle_belief_rollup.py -v`
Expected: FAIL — `ImportError: cannot import name 'MemberBelief'`.

- [ ] **Step 3: Add the dataclasses + roll-up function to `bundle_belief.py`**

Add these imports at the top of `bundle_belief.py`:

```python
from dataclasses import dataclass

from .belief import BeliefMagnitude, BeliefResult, _MAG_ORDER
from .belief_scalar import BeliefScalar
```

Add the dataclasses and functions:

```python
@dataclass(frozen=True)
class MemberBelief:
    member_uri: str
    belief: BeliefResult
    scalar: BeliefScalar | None
    rank_key: tuple
    reason: str | None = None


@dataclass(frozen=True)
class BundleBeliefResult:
    composition_rule: str
    magnitude: BeliefMagnitude          # = member_results[0].belief.magnitude (the min-rank_key member)
    capped_by_refutation: bool
    contested: bool
    scalar: BeliefScalar | None         # the min-rank_key member's band (the scalar driver = member_results[0])
    member_results: list[MemberBelief]  # sorted ascending by rank_key; [0] drives magnitude + scalar
    bottleneck_members: list[str]       # ORDINAL-only: members sharing the minimum magnitude (superset of the scalar driver)
    contested_members: list[str]
    unresolved_members: list[str]


def member_rank_key(belief: BeliefResult, scalar: BeliefScalar | None, member_uri: str) -> tuple:
    """Deterministic ascending order: ordinal magnitude, then scalar net-band lower
    (0.0 when the scalar layer is off), then member_uri as a total-order tiebreak."""
    lower = scalar.net_band[0] if scalar is not None else 0.0
    return (_MAG_ORDER.index(belief.magnitude), lower, member_uri)


def roll_up_weakest_link(members: list[MemberBelief], *, rule: CompositionRule) -> BundleBeliefResult:
    """v1 conjunction: the bundle is as believed as its weakest member.

    Refutation propagates as a SEPARATE boolean axis (OR across members), never
    folded into the magnitude ordinal.

    `bottleneck_members` is the ORDINAL-tied set — every member sharing the minimum
    magnitude (the explanatory "weakest-magnitude members"). The reported `magnitude`
    and `scalar` come from `member_results[0]` (minimum full `rank_key`), which is
    always within that set; when several members tie on ordinal but differ in
    net-band, `[0]` is the deterministic scalar driver and the others are still
    listed as bottlenecks for explanation. Every member's `scalar`/`rank_key` is
    retained in `member_results`, so the scalar driver is always identifiable.
    """
    ordered = sorted(members, key=lambda m: m.rank_key)
    bottleneck = ordered[0]
    bundle_magnitude = bottleneck.belief.magnitude
    return BundleBeliefResult(
        composition_rule=rule.value,
        magnitude=bundle_magnitude,
        capped_by_refutation=any(m.belief.capped_by_refutation for m in ordered),
        contested=any(m.belief.contested for m in ordered),
        scalar=bottleneck.scalar,
        member_results=ordered,
        bottleneck_members=[m.member_uri for m in ordered if m.belief.magnitude == bundle_magnitude],
        contested_members=[m.member_uri for m in ordered if m.belief.contested],
        unresolved_members=[m.member_uri for m in ordered if m.belief.magnitude == BeliefMagnitude.SPECULATIVE],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest science/tests/test_bundle_belief_rollup.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/bundle_belief.py science/tests/test_bundle_belief_rollup.py
git commit -m "feat(graph): weakest-link bundle roll-up with separate refutation axis"
```

---

### Task 5: `belief_for_entity` dispatch (pass-through / roll-up / zero-member hard-fail / reserved guard)

**Files:**
- Modify: `science/src/science_tool/graph/bundle_belief.py`
- Test: `science/tests/test_bundle_belief_rollup.py` (extend)

- [ ] **Step 1: Write the failing test (append to the existing file)**

```python
# append to science/tests/test_bundle_belief_rollup.py
import pytest
from rdflib import Graph, Literal, RDF, URIRef

from science_tool.graph.belief import EVIDENCE_LINE_CLASS
from science_tool.graph.bundle_belief import belief_for_entity, UnresolvedBundleError
from science_tool.graph.io import CITO_NS, SCI_NS

HYP = URIRef("http://example.org/science/entity/hypothesis/h1")
MECH = URIRef("http://example.org/science/entity/mechanism/m1")
PA = URIRef("http://example.org/science/entity/proposition/pa")
PB = URIRef("http://example.org/science/entity/proposition/pb")


def _supported_line(k, prov, target, gid):
    line = URIRef(f"http://example.org/science/entity/evidence-line/{gid}")
    k.add((line, RDF.type, EVIDENCE_LINE_CLASS))
    k.add((line, CITO_NS.supports, target))
    prov.add((line, SCI_NS.evidenceStrength, Literal("strong")))
    prov.add((line, SCI_NS.evidenceRole, Literal("direct_test")))
    prov.add((line, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    prov.add((line, SCI_NS.independenceGroup, Literal(gid)))
    prov.add((line, SCI_NS.evidenceIndependence, Literal("independent")))


def test_proposition_passes_through_to_belief_result():
    from science_tool.graph.belief import BeliefResult
    k, prov = Graph(), Graph()
    k.add((PA, RDF.type, SCI_NS.Proposition))
    result = belief_for_entity(k, prov, PA, scalar_enabled=False)
    assert isinstance(result, BeliefResult)


def test_mechanism_rolls_up_weakest_link():
    k, prov = Graph(), Graph()
    k.add((MECH, RDF.type, SCI_NS.Mechanism))
    for p in (PA, PB):
        k.add((p, RDF.type, SCI_NS.Proposition))
        k.add((MECH, SCI_NS.hasProposition, p))
    # PA gets two independent strong supports (well_supported); PB gets none (speculative).
    _supported_line(k, prov, PA, "g1")
    _supported_line(k, prov, PA, "g2")
    result = belief_for_entity(k, prov, MECH, scalar_enabled=False)
    from science_tool.graph.bundle_belief import BundleBeliefResult
    from science_tool.graph.belief import BeliefMagnitude
    assert isinstance(result, BundleBeliefResult)
    assert result.magnitude == BeliefMagnitude.SPECULATIVE  # PB is the bottleneck
    assert str(PB) in result.bottleneck_members


def test_mechanism_with_zero_resolved_members_hard_fails():
    k, prov = Graph(), Graph()
    k.add((MECH, RDF.type, SCI_NS.Mechanism))
    # hasProposition points at a non-existent / non-Proposition node
    k.add((MECH, SCI_NS.hasProposition, URIRef("http://example.org/science/entity/proposition/missing")))
    with pytest.raises(UnresolvedBundleError):
        belief_for_entity(k, prov, MECH, scalar_enabled=False)


def test_undecomposed_hypothesis_no_rule_falls_back():
    from science_tool.graph.belief import BeliefResult
    k, prov = Graph(), Graph()
    k.add((HYP, RDF.type, SCI_NS.Hypothesis))  # no members, no authored rule
    result = belief_for_entity(k, prov, HYP, scalar_enabled=False)
    assert isinstance(result, BeliefResult)  # graceful: its own (empty) evidence


def test_authored_rule_with_zero_members_hard_fails():
    k, prov = Graph(), Graph()
    k.add((HYP, RDF.type, SCI_NS.Hypothesis))
    prov.add((HYP, SCI_NS.compositionRule, Literal("conjunctive")))
    with pytest.raises(UnresolvedBundleError):
        belief_for_entity(k, prov, HYP, scalar_enabled=False)


def test_reserved_rule_in_graph_raises_not_implemented():
    # Defensive engine guard: even if a reserved rule bypasses model validation and lands
    # in the graph, the engine refuses it rather than silently treating it as weakest-link.
    k, prov = Graph(), Graph()
    k.add((MECH, RDF.type, SCI_NS.Mechanism))
    k.add((PA, RDF.type, SCI_NS.Proposition))
    k.add((MECH, SCI_NS.hasProposition, PA))
    prov.add((MECH, SCI_NS.compositionRule, Literal("evidence_union")))
    with pytest.raises(NotImplementedError):
        belief_for_entity(k, prov, MECH, scalar_enabled=False)


def test_composition_rule_on_non_bundle_in_graph_raises():
    k, prov = Graph(), Graph()
    k.add((PA, RDF.type, SCI_NS.Proposition))
    prov.add((PA, SCI_NS.compositionRule, Literal("conjunctive")))
    with pytest.raises(ValueError, match="not a bundle"):
        belief_for_entity(k, prov, PA, scalar_enabled=False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_bundle_belief_rollup.py -v`
Expected: FAIL — `ImportError: cannot import name 'belief_for_entity'`.

- [ ] **Step 3: Add the dispatch function + error to `bundle_belief.py`**

Add imports:

```python
from .belief import aggregate_belief, collect_evidence_units
from .belief_scalar import belief_scalar
from science_model.reasoning import RESERVED_COMPOSITION_RULES
```

Add:

```python
class UnresolvedBundleError(ValueError):
    """An authored bundle (or any mechanism) resolved to zero member propositions."""


def belief_for_entity(knowledge, provenance, uri, *, scalar_enabled: bool):
    """Dispatch: proposition → BeliefResult; hypothesis/mechanism → BundleBeliefResult.

    Returns BeliefResult | BundleBeliefResult.
    """
    rule_literal = provenance.value(uri, SCI_NS.compositionRule)
    authored_rule = CompositionRule(str(rule_literal)) if rule_literal is not None else None
    if authored_rule in RESERVED_COMPOSITION_RULES:
        # Defensive: the model layer already rejects these at parse; never silently fall back.
        raise NotImplementedError(
            f"composition_rule {authored_rule.value!r} is reserved and not implemented in v1 "
            "(see docs/plans/2026-06-11-bundle-belief-rollup-design.md §4)."
        )

    kind = bundle_kind(knowledge, uri)
    if kind is None:
        if authored_rule is not None:
            # Defense in depth: the model layer rejects composition_rule on non-bundle kinds,
            # but a hand-authored graph could still carry one. Never silently ignore it.
            raise ValueError(
                f"{uri} carries composition_rule {authored_rule.value!r} but is not a bundle "
                "(hypothesis/mechanism); composition_rule is meaningless on non-bundle entities."
            )
        return aggregate_belief(collect_evidence_units(knowledge, provenance, [uri]))

    members = bundle_members(knowledge, uri)
    if not members:
        if authored_rule is not None or kind == "mechanism":
            raise UnresolvedBundleError(
                f"{uri} is a {kind} bundle with zero resolved member propositions "
                "(dangling has_proposition / discusses links?); refusing to collapse to "
                "direct-evidence belief."
            )
        return aggregate_belief(collect_evidence_units(knowledge, provenance, [uri]))

    rule = authored_rule or _KIND_DEFAULT_RULE[kind]
    member_beliefs: list[MemberBelief] = []
    for member in members:
        belief = aggregate_belief(collect_evidence_units(knowledge, provenance, [member]))
        scalar = belief_scalar(belief) if scalar_enabled else None
        reason = "speculative: no evidence" if belief.magnitude == BeliefMagnitude.SPECULATIVE else None
        member_beliefs.append(
            MemberBelief(
                member_uri=str(member),
                belief=belief,
                scalar=scalar,
                rank_key=member_rank_key(belief, scalar, str(member)),
                reason=reason,
            )
        )
    return roll_up_weakest_link(member_beliefs, rule=rule)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --frozen pytest science/tests/test_bundle_belief_rollup.py -v`
Expected: PASS (all 9 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/bundle_belief.py science/tests/test_bundle_belief_rollup.py
git commit -m "feat(graph): belief_for_entity dispatch with zero-member hard-fail and reserved-rule guard"
```

---

## Phase 3 — snapshot wiring + coverage relabel

### Task 6: Emit bundle rows (hypothesis + mechanism) via the engine

**Files:**
- Modify: `science/src/science_tool/graph/belief_snapshot.py`
- Test: `science/tests/test_bundle_belief_snapshot.py` (create); update `science/tests/test_belief_snapshot.py` if it asserts old hypothesis behavior.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_bundle_belief_snapshot.py
from __future__ import annotations

from rdflib import Graph, Literal, RDF, URIRef

from science_tool.graph.belief import EVIDENCE_LINE_CLASS
from science_tool.graph.belief_snapshot import snapshot_records
from science_tool.graph.io import CITO_NS, SCI_NS

MECH = URIRef("http://example.org/science/entity/mechanism/m1")
PA = URIRef("http://example.org/science/entity/proposition/pa")
PB = URIRef("http://example.org/science/entity/proposition/pb")


def _strong(k, prov, target, gid):
    line = URIRef(f"http://example.org/science/entity/evidence-line/{gid}")
    k.add((line, RDF.type, EVIDENCE_LINE_CLASS))
    k.add((line, CITO_NS.supports, target))
    for pred, val in [
        (SCI_NS.evidenceStrength, "strong"), (SCI_NS.evidenceRole, "direct_test"),
        (SCI_NS.evidenceType, "empirical_data_evidence"), (SCI_NS.independenceGroup, gid),
        (SCI_NS.evidenceIndependence, "independent"),
    ]:
        prov.add((line, pred, Literal(val)))


def test_snapshot_emits_mechanism_bundle_row():
    k, prov = Graph(), Graph()
    k.add((MECH, RDF.type, SCI_NS.Mechanism))
    for p in (PA, PB):
        k.add((p, RDF.type, SCI_NS.Proposition))
        k.add((MECH, SCI_NS.hasProposition, p))
    _strong(k, prov, PA, "g1")
    _strong(k, prov, PA, "g2")
    _strong(k, prov, PB, "g3")
    rows = snapshot_records(k, prov, scalar_enabled=False, as_of="2026-06-11")
    mech_rows = [r for r in rows if r["claim"] == str(MECH)]
    assert len(mech_rows) == 1
    row = mech_rows[0]
    assert row["is_bundle"] is True
    assert row["composition_rule"] == "all_steps"
    assert "bottleneck_members" in row
    assert "capped_by_refutation" in row
    # _key()/append_snapshots contract (belief_snapshot.py:72): bundle rows MUST carry
    # input_hashes + scalar_enabled or append raises KeyError.
    from science_tool.graph.belief_snapshot import _key
    assert row["input_hashes"]            # non-empty member-evidence + structure hashes
    assert row["scalar_enabled"] is False
    _key(row)                             # must not raise


def test_snapshot_bundle_rows_are_appendable(tmp_path):
    from science_tool.graph.belief_snapshot import append_snapshots
    k, prov = Graph(), Graph()
    k.add((MECH, RDF.type, SCI_NS.Mechanism))
    k.add((PA, RDF.type, SCI_NS.Proposition))
    k.add((MECH, SCI_NS.hasProposition, PA))
    _strong(k, prov, PA, "g1")
    rows = snapshot_records(k, prov, scalar_enabled=False, as_of="2026-06-11")
    path = tmp_path / "snapshots.jsonl"
    assert append_snapshots(path, rows) == len(rows)   # no KeyError; all rows written
    assert append_snapshots(path, rows) == 0           # idempotent: same key dedupes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest science/tests/test_bundle_belief_snapshot.py -v`
Expected: FAIL — no mechanism row (mechanisms aren't iterated) / missing `is_bundle` key.

- [ ] **Step 3: Rewire `snapshot_records`**

In `belief_snapshot.py`: extend `_claim_uris` to also yield `SCI_NS.Mechanism`, and in `snapshot_records` dispatch through `belief_for_entity`. Replace the body of `snapshot_records`:

```python
from .bundle_belief import BundleBeliefResult, belief_for_entity


def _claim_uris(knowledge):
    seen: set[URIRef] = set()
    for ctype in (SCI_NS.Proposition, SCI_NS.Hypothesis, SCI_NS.Mechanism):
        for subj, _, _ in knowledge.triples((None, RDF.type, ctype)):
            if isinstance(subj, URIRef) and subj not in seen:
                seen.add(subj)
                yield subj


def snapshot_records(knowledge, provenance, *, scalar_enabled: bool, as_of: str) -> list[dict]:
    rows: list[dict] = []
    for claim in _claim_uris(knowledge):
        result = belief_for_entity(knowledge, provenance, claim, scalar_enabled=scalar_enabled)

        if isinstance(result, BundleBeliefResult):
            member_uris = [URIRef(m.member_uri) for m in result.member_results]
            scalar = result.scalar
            # Reproducibility key (_key() requires input_hashes + scalar_enabled):
            # hashes of every member evidence-line input, PLUS a synthetic hash of
            # (composition_rule, sorted member ids) so a membership or rule change yields
            # a new snapshot row even when no underlying evidence line changed.
            member_units = collect_evidence_units(knowledge, provenance, member_uris)
            line_hashes = {_line_content_hash(knowledge, provenance, URIRef(u.line_uri)) for u in member_units}
            structure = "\n".join([result.composition_rule, *sorted(str(u) for u in member_uris)])
            structure_hash = "sha256:" + hashlib.sha256(structure.encode("utf-8")).hexdigest()
            input_hashes = sorted(line_hashes | {structure_hash})
            rows.append({
                "as_of": as_of,
                "claim": str(claim),
                "is_bundle": True,
                "composition_rule": result.composition_rule,
                "belief_state": result.magnitude.value,
                "capped_by_refutation": result.capped_by_refutation,
                "contested": result.contested,
                "bottleneck_members": result.bottleneck_members,
                "scalar_driver_member": (result.member_results[0].member_uri if result.member_results else None),
                "contested_members": result.contested_members,
                "unresolved_members": result.unresolved_members,
                "member_count": len(member_uris),
                "scalar_enabled": scalar_enabled,
                "net_band": list(scalar.net_band) if (scalar_enabled and scalar) else None,
                "net_robust": scalar.net_robust if (scalar_enabled and scalar) else None,
                "input_hashes": input_hashes,
                "config_version": CONFIG_VERSION,
            })
            continue

        # Plain proposition (or undecomposed-hypothesis fallback).
        units = collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, claim))
        if not units:
            continue
        scalar = belief_scalar(result)
        input_hashes = sorted({_line_content_hash(knowledge, provenance, URIRef(u.line_uri)) for u in units})
        rows.append({
            "as_of": as_of,
            "claim": str(claim),
            "is_bundle": False,
            "belief_state": result.magnitude.value,
            "contested": result.contested,
            "diagnostic_dispute_count": scalar.diagnostic_dispute_count,
            "scalar_enabled": scalar_enabled,
            "massed_support_score": scalar.massed_support_score if scalar_enabled else None,
            "massed_dispute_score": scalar.massed_dispute_score if scalar_enabled else None,
            "massed_support_band": list(scalar.massed_support_band) if scalar_enabled else None,
            "massed_dispute_band": list(scalar.massed_dispute_band) if scalar_enabled else None,
            "net_band": list(scalar.net_band) if scalar_enabled else None,
            "net_robust": scalar.net_robust if scalar_enabled else None,
            "input_hashes": input_hashes,
            "config_version": CONFIG_VERSION,
        })
    rows.sort(key=lambda r: r["claim"])
    return rows
```

Note: the plain branch is reached **only** for (a) propositions and (b) an undecomposed hypothesis that resolved to zero members. For a proposition, `_evidence_targets_for_uri` returns `[uri]` — identical to `belief_for_entity`'s non-bundle path, so `result.magnitude` and the recomputed `units` agree. For the zero-member hypothesis fallback, there are by definition no `hasProposition`/`cito:discusses` links (else `bundle_members` would be non-empty and it would take the bundle branch), so `_evidence_targets_for_uri` also returns just `[uri]` — they agree *in this case*. The equivalence is **not** general (`_evidence_targets_for_uri` expands a hypothesis with linked claims; `belief_for_entity` non-bundle does not) — it holds only because the fallback is members-empty. A hypothesis **with** members now reports the **roll-up** belief, never the coverage-union; the coverage union remains available via `evidence_signals.py` for other surfaces (design §7: coverage is a signal, not the belief).

- [ ] **Step 4: Run the new test + the existing snapshot test**

Run: `uv run --frozen pytest science/tests/test_bundle_belief_snapshot.py science/tests/test_belief_snapshot.py -v`
Expected: new test PASS. If `test_belief_snapshot.py` fails because it asserted a hypothesis's old coverage-union `belief_state` or the new rows now carry `is_bundle`, update those assertions to match the roll-up semantics (a hypothesis with members now reports its weakest member's magnitude) and re-run. Do **not** weaken a test to hide a real behavior change — update it to assert the new, correct behavior.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief_snapshot.py science/tests/test_bundle_belief_snapshot.py science/tests/test_belief_snapshot.py
git commit -m "feat(graph): snapshot bundle rows for hypothesis+mechanism via roll-up; coverage union no longer the bundle belief"
```

---

## Phase 4 — documentation

### Task 7: Update the canonical proposition model

**Files:**
- Modify: `science/docs/proposition-and-evidence-model.md`

- [ ] **Step 1: Update the hypothesis roll-up references**

The doc (lines 38, 88, 271) names hypothesis roll-up as a derived field. Add a short subsection under "Authored Versus Derived Fields" → "Derived Fields" (after the `hypothesis roll-ups across linked propositions` bullet) recording that roll-up is now implemented and how:

```markdown
### Bundle belief roll-up (hypotheses and mechanisms)

A `hypothesis` or `mechanism` with member propositions carries a **derived**
bundle belief, computed from its members under an authored `composition_rule`
(`all_steps` for mechanisms, `conjunctive` for hypotheses; both implemented as
**weakest-link** — the bundle is as believed as its least-believed member).
Refutation propagates as a separate `capped_by_refutation` flag, never a new
ordinal. Member belief reuses the per-proposition pipeline and its independence
reduction unchanged; weakest-link is independence-safe because `min` does not sum
shared sources across members. The reserved rules `evidence_union` /
`faceted_support` are not implemented and are rejected at authoring time. See
`docs/plans/2026-06-11-bundle-belief-rollup-design.md`. The older hypothesis
evidence-union path is an **evidence-coverage signal**, not the bundle's belief.
```

- [ ] **Step 2: Commit**

```bash
git add science/docs/proposition-and-evidence-model.md
git commit -m "docs: record bundle belief roll-up (weakest-link v1) in the canonical proposition model"
```

---

## Final verification (after all tasks)

- [ ] Run the focused suite for everything touched:

```bash
uv run --frozen pytest science/tests/test_composition_rule_field.py science/tests/test_composition_rule_materialize.py science/tests/test_bundle_members.py science/tests/test_bundle_belief_rollup.py science/tests/test_bundle_belief_snapshot.py science/tests/test_belief_snapshot.py -v
```

- [ ] Run the full belief/graph regression (catch any snapshot/materialize consumers):

```bash
uv run --frozen pytest science/tests -m "not snapshot and not real_projects" -q
```

- [ ] Lint:

```bash
uv run --frozen ruff check science/src/science_tool/graph/bundle_belief.py science/src/science_tool/graph/belief_snapshot.py science/model/src/science_model
```

Expected: green suite (exit 0, zero FAILED/ERROR), no new ruff findings in the touched files.

---

## Notes for the implementer

- **Independence is not re-implemented.** Per-member belief goes through the existing `aggregate_belief(collect_evidence_units(...))`, which already runs the independence reduction. Weakest-link (`min`) does not sum across members, so no cross-member independence pass is needed (design §5). Do not add one.
- **No new ordinal for refutation.** `BeliefMagnitude` stays `speculative→fragile→supported→well_supported`. Refutation is the boolean `capped_by_refutation`, OR'd across members. Resist the urge to invent an `eliminated`/`refuted` magnitude — the legacy MM30 `edge_status` had one, the proposition model deliberately does not.
- **Fail early, no silent fallback.** A reserved rule and a zero-member authored bundle both raise. Do not catch-and-default.
- **Determinism.** `member_rank_key` ends in `member_uri`, so ordering is total even when magnitudes and bands tie — keep it.
