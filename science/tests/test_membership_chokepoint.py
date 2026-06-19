from __future__ import annotations

import pytest
from rdflib import Graph, Literal, RDF

from science_model.reasoning import MembershipRole
from science_tool.graph.io import (
    CITO_NS,
    SCI_NS,
    emit_discusses_membership,
    membership_uri_for,
    entity_uri_for_ref,
)


def _emit(role=MembershipRole.CORE, frame_cid="hypothesis:0001-foo"):
    g = Graph()
    prop_cid = "proposition:0011-bar"
    emit_discusses_membership(
        g,
        prop_uri=entity_uri_for_ref(prop_cid),
        frame_uri=entity_uri_for_ref(frame_cid),
        prop_cid=prop_cid,
        frame_cid=frame_cid,
        role=role,
    )
    return g, prop_cid, frame_cid


def test_plain_triple_always_emitted():
    g, prop_cid, frame_cid = _emit()
    assert (entity_uri_for_ref(prop_cid), CITO_NS.discusses, entity_uri_for_ref(frame_cid)) in g


def test_core_membership_node_emitted():
    g, prop_cid, frame_cid = _emit(role=MembershipRole.CORE)
    node = membership_uri_for(prop_cid, frame_cid)
    assert (node, RDF.type, SCI_NS.BundleMembership) in g
    assert (node, SCI_NS.membershipProposition, entity_uri_for_ref(prop_cid)) in g
    assert (node, SCI_NS.membershipFrame, entity_uri_for_ref(frame_cid)) in g
    assert (node, SCI_NS.membershipRole, Literal("core")) in g


def test_background_role_recorded():
    g, prop_cid, frame_cid = _emit(role=MembershipRole.BACKGROUND)
    node = membership_uri_for(prop_cid, frame_cid)
    assert (node, SCI_NS.membershipRole, Literal("background")) in g


def test_non_bundle_frame_loud_fails():
    with pytest.raises(ValueError, match="not a bundle"):
        _emit(frame_cid="topic:0003-context")
