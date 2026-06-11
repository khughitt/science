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
