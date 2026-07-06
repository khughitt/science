"""Tests that bridge_between_refs emits a BundleMembership role node via the chokepoint."""

from pathlib import Path

import pytest
from conftest import build_entity_graph
from rdflib import Literal, URIRef
from rdflib.namespace import RDF

from science_tool.graph.io import CITO_NS, SCI_NS, membership_uri_for
from science_tool.graph.store import (
    PROJECT_NS,
    _graph_uri,
    _load_dataset,
)


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Materialized source-authored bridge proposition graph."""
    return build_entity_graph(
        tmp_path,
        [
            _entity("hypothesis", "0001-foo", "Foo hypothesis"),
            _entity(
                "proposition",
                "bridge-prop-01",
                "Bridging proposition",
                discusses=[{"frame": "hypothesis:0001-foo", "role": "core"}],
            ),
        ],
        relations=[
            {
                "subject": "proposition:bridge-prop-01",
                "predicate": "sci:bridgeBetween",
                "object": "hypothesis:0001-foo",
                "graph_layer": "graph/provenance",
            }
        ],
    )


def _entity(kind: str, entity_id: str, title: str, **frontmatter: object) -> dict:
    return {
        "kind": kind,
        "id": entity_id,
        "frontmatter": {"title": title, **frontmatter},
        "body": f"{title}\n",
    }


class TestBridgeBetweenMembership:
    def test_bridge_emits_discusses_triple(self, graph_path: Path) -> None:
        """(prop, cito:discusses, hypothesis) triple must exist after materialization."""
        dataset = _load_dataset(graph_path)
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))

        prop_uri = URIRef(PROJECT_NS["proposition/bridge-prop-01"])
        hyp_uri = URIRef(PROJECT_NS["hypothesis/0001-foo"])

        assert (prop_uri, CITO_NS.discusses, hyp_uri) in knowledge, (
            "Expected (prop, cito:discusses, hypothesis) triple in knowledge graph"
        )

    def test_bridge_emits_bundle_membership_node(self, graph_path: Path) -> None:
        """A BundleMembership node with membershipRole 'core' must be created."""
        dataset = _load_dataset(graph_path)
        knowledge = dataset.graph(_graph_uri("graph/knowledge"))

        prop_cid = "proposition:bridge-prop-01"
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
        dataset = _load_dataset(graph_path)
        provenance = dataset.graph(_graph_uri("graph/provenance"))

        prop_uri = URIRef(PROJECT_NS["proposition/bridge-prop-01"])
        hyp_uri = URIRef(PROJECT_NS["hypothesis/0001-foo"])

        assert (prop_uri, SCI_NS.bridgeBetween, hyp_uri) in provenance, (
            "Expected (prop, sci:bridgeBetween, hypothesis) triple in provenance graph"
        )
