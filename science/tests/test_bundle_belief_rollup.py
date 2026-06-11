# science/tests/test_bundle_belief_rollup.py
from __future__ import annotations

import pytest
from rdflib import Graph, Literal, RDF, URIRef

from science_model.reasoning import CompositionRule
from science_tool.graph.belief import BeliefMagnitude, BeliefResult, EVIDENCE_LINE_CLASS
from science_tool.graph.bundle_belief import (
    BundleBeliefResult,
    MemberBelief,
    UnresolvedBundleError,
    belief_for_entity,
    member_rank_key,
    roll_up_weakest_link,
)
from science_tool.graph.io import CITO_NS, SCI_NS


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


# ---------------------------------------------------------------------------
# Task 5: belief_for_entity dispatch
# ---------------------------------------------------------------------------

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
