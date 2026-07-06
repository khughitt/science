"""Tests that bridge_between_refs emits a BundleMembership role node via the chokepoint."""

from pathlib import Path

import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import RDF

from science_tool.graph.io import CITO_NS, SCI_NS, membership_uri_for
from science_tool.graph.store import (
    INITIAL_GRAPH_TEMPLATE,
    PROJECT_NS,
    _graph_uri,
    _load_dataset,
    _slug,
    add_hypothesis,
    add_proposition,
)


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for testing."""
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return gp


class TestBridgeBetweenMembership:
    def test_bridge_emits_discusses_triple(self, graph_path: Path) -> None:
        """(prop, cito:discusses, hypothesis) triple must exist after add_proposition with bridge_between_refs."""
        add_hypothesis(graph_path, "0001-foo", "Foo hypothesis", source="paper:doi_test")
        prop_uri = add_proposition(
            graph_path,
            text="Bridging proposition",
            source="paper:doi_test",
            proposition_id="bridge-prop-01",
            bridge_between_refs=["hypothesis:0001-foo"],
        )

        dataset = _load_dataset(graph_path)
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))

        hyp_uri = URIRef(PROJECT_NS["hypothesis/0001-foo"])

        assert (prop_uri, CITO_NS.discusses, hyp_uri) in knowledge, (
            "Expected (prop, cito:discusses, hypothesis) triple in knowledge graph"
        )

    def test_bridge_emits_bundle_membership_node(self, graph_path: Path) -> None:
        """A BundleMembership node with membershipRole 'core' must be created."""
        add_hypothesis(graph_path, "0001-foo", "Foo hypothesis", source="paper:doi_test")
        add_proposition(
            graph_path,
            text="Bridging proposition",
            source="paper:doi_test",
            proposition_id="bridge-prop-01",
            bridge_between_refs=["hypothesis:0001-foo"],
        )

        dataset = _load_dataset(graph_path)
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))

        token = _slug("bridge-prop-01")
        prop_cid = f"proposition:{token}"
        frame_cid = "hypothesis:0001-foo"
        node = membership_uri_for(prop_cid, frame_cid)

        assert (node, RDF.type, SCI_NS.BundleMembership) in knowledge, (
            "Expected BundleMembership rdf:type triple"
        )
        assert (node, SCI_NS.membershipRole, Literal("core")) in knowledge, (
            "Expected membershipRole 'core' on the BundleMembership node"
        )

    def test_bridge_keeps_provenance_bridge_between_triple(self, graph_path: Path) -> None:
        """(prop, sci:bridgeBetween, hypothesis) provenance triple must still be present."""
        add_hypothesis(graph_path, "0001-foo", "Foo hypothesis", source="paper:doi_test")
        prop_uri = add_proposition(
            graph_path,
            text="Bridging proposition",
            source="paper:doi_test",
            proposition_id="bridge-prop-01",
            bridge_between_refs=["hypothesis:0001-foo"],
        )

        dataset = _load_dataset(graph_path)
        provenance = dataset.graph(_graph_uri("graph/provenance"))

        hyp_uri = URIRef(PROJECT_NS["hypothesis/0001-foo"])

        assert (prop_uri, SCI_NS.bridgeBetween, hyp_uri) in provenance, (
            "Expected (prop, sci:bridgeBetween, hypothesis) triple in provenance graph"
        )
