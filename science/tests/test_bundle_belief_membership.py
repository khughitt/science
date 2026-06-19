from __future__ import annotations

from rdflib import Graph, Literal, RDF, URIRef

from science_model.reasoning import MembershipRole
from science_tool.graph.bundle_belief import core_members, membership_role
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS


def _membership(g, prop, frame, role):
    m = PROJECT_NS[f"membership/{str(prop)}__{str(frame)}".replace(":", "_").replace("/", "_")]
    g.add((m, RDF.type, SCI_NS.BundleMembership))
    g.add((m, SCI_NS.membershipProposition, prop))
    g.add((m, SCI_NS.membershipFrame, frame))
    g.add((m, SCI_NS.membershipRole, Literal(role)))


def _bundle_graph():
    g = Graph()
    hyp = URIRef("urn:h1")
    core, rival, bg = URIRef("urn:p_core"), URIRef("urn:p_rival"), URIRef("urn:p_bg")
    g.add((hyp, RDF.type, SCI_NS.Hypothesis))
    for p in (core, rival, bg):
        g.add((p, RDF.type, SCI_NS.Proposition))
        g.add((p, CITO_NS.discusses, hyp))
    _membership(g, core, hyp, "core")
    _membership(g, rival, hyp, "rival")
    _membership(g, bg, hyp, "background")
    return g, hyp, core, rival, bg


def test_membership_role_reads_node():
    g, hyp, core, rival, bg = _bundle_graph()
    assert membership_role(g, core, hyp) == MembershipRole.CORE
    assert membership_role(g, rival, hyp) == MembershipRole.RIVAL
    assert membership_role(g, bg, hyp) == MembershipRole.BACKGROUND


def test_membership_role_defaults_core_when_absent():
    g = Graph()
    p, hyp = URIRef("urn:p"), URIRef("urn:h")
    assert membership_role(g, p, hyp) == MembershipRole.CORE


def test_core_members_excludes_rival_and_background():
    g, hyp, core, rival, bg = _bundle_graph()
    assert core_members(g, hyp) == [core]


def test_has_proposition_is_authoritatively_core():
    # A proposition that is BOTH a mechanism step (hasProposition) AND discussed as a
    # rival of the same frame must stay core — forward membership wins (spec §3.3).
    g = Graph()
    mech, step = URIRef("urn:m1"), URIRef("urn:p_step")
    g.add((mech, RDF.type, SCI_NS.Mechanism))
    g.add((step, RDF.type, SCI_NS.Proposition))
    g.add((mech, SCI_NS.hasProposition, step))
    g.add((step, CITO_NS.discusses, mech))
    _membership(g, step, mech, "rival")  # contradictory authoring; forward wins
    assert membership_role(g, step, mech) == MembershipRole.RIVAL
    assert core_members(g, mech) == [step]
