from __future__ import annotations

import dataclasses

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from science_tool.graph.belief import EVIDENCE_LINE_CLASS, EvidenceUnit
from science_tool.graph.belief_basis import NO_TYPED_ENTITIES, EntityBasis, basis_digest, capture_basis, unit_key
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS


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
    unit = dataclasses.replace(_u(), source=object())
    with pytest.raises(TypeError):
        unit_key(unit)


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
