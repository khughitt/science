"""Tests that bridge_between_refs emits a BundleMembership role node via the chokepoint."""

from pathlib import Path

import pytest
from click.testing import CliRunner
from rdflib import Literal, URIRef
from rdflib.namespace import RDF

from rdflib import Dataset

from science_tool.cli import main
from science_tool.graph.io import SCI_NS, CITO_NS, membership_uri_for
from science_tool.graph.store import (
    DEFAULT_GRAPH_PATH,
    INITIAL_GRAPH_TEMPLATE,
    PROJECT_NS,
    add_hypothesis,
    add_proposition,
    _graph_uri,
    _load_dataset,
    _slug,
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


class TestBridgeRoleCli:
    def test_bridge_role_background_via_cli(self) -> None:
        """--bridge-role background must produce a BundleMembership with membershipRole 'background'."""
        runner = CliRunner()

        with runner.isolated_filesystem():
            assert runner.invoke(main, ["graph", "init"]).exit_code == 0
            assert (
                runner.invoke(
                    main,
                    [
                        "graph",
                        "add",
                        "hypothesis",
                        "0001-foo",
                        "--text",
                        "Foo hypothesis",
                        "--source",
                        "paper:doi_test",
                    ],
                ).exit_code
                == 0
            )
            result = runner.invoke(
                main,
                [
                    "graph",
                    "add",
                    "proposition",
                    "Bridging proposition",
                    "--source",
                    "paper:doi_test",
                    "--id",
                    "bridge-prop-01",
                    "--bridge-between",
                    "hypothesis:0001-foo",
                    "--bridge-role",
                    "background",
                ],
            )
            assert result.exit_code == 0, result.output

            dataset = Dataset()
            dataset.parse(source=str(DEFAULT_GRAPH_PATH), format="trig")
            knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

            token = _slug("bridge-prop-01")
            prop_cid = f"proposition:{token}"
            frame_cid = "hypothesis:0001-foo"
            node = membership_uri_for(prop_cid, frame_cid)

            assert (node, RDF.type, SCI_NS.BundleMembership) in knowledge, (
                "Expected BundleMembership rdf:type triple"
            )
            assert (node, SCI_NS.membershipRole, Literal("background")) in knowledge, (
                "Expected membershipRole 'background' on the BundleMembership node"
            )
