from pathlib import Path

import pytest
from rdflib.namespace import RDF

from conftest import build_entity_graph
from science_tool.graph.store import (
    PROJECT_NS,
    SCI_NS,
    _graph_uri,
    _load_dataset,
    init_graph_file,
)


@pytest.fixture()
def tmp_graph(tmp_path: Path) -> Path:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    init_graph_file(graph_path)
    return graph_path


def _source_entity(kind: str, entity_id: str, title: str, *, status: str = "active") -> dict:
    return {
        "kind": kind,
        "id": entity_id,
        "frontmatter": {
            "title": title,
            "status": status,
            "related": [],
            "source_refs": [],
        },
        "body": f"{title}\n",
    }


# Retired finding/interpretation writer assertions for sci:contains and sci:groundedBy
# are intentionally pruned. Source-emitted mechanism composition coverage lives in
# test_graph_materialize::test_materialize_graph_emits_mechanism_participants_and_propositions.
# The retired add_finding invalid-confidence mutator-validation test is also
# pruned: source-authored finding entities do not have an equivalent schema
# validator for the old string confidence ladder.


def test_source_authored_finding_materializes(tmp_path: Path) -> None:
    graph_path = build_entity_graph(
        tmp_path,
        [
            _source_entity("proposition", "p1", "X correlates with Y", status="active"),
            _source_entity("observation", "obs1", "r=0.73"),
            _source_entity("finding", "f01", "Analysis shows X-Y correlation"),
        ],
    )
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    finding_uri = PROJECT_NS["finding/f01"]
    assert (finding_uri, RDF.type, SCI_NS.Finding) in knowledge


def test_source_authored_interpretation_materializes(tmp_path: Path) -> None:
    graph_path = build_entity_graph(
        tmp_path,
        [
            _source_entity("proposition", "p1", "X causes Y", status="active"),
            _source_entity("observation", "obs1", "r=0.73"),
            _source_entity("finding", "f01", "Correlation found"),
            _source_entity("interpretation", "interp-01", "Initial expression analysis suggests X-Y link"),
        ],
    )
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    interp_uri = PROJECT_NS["interpretation/interp-01"]
    assert (interp_uri, RDF.type, SCI_NS.Interpretation) in knowledge


def test_source_authored_evidence_chain_materializes(tmp_graph: Path) -> None:
    """Source-authored observation/proposition/finding entities materialize after composition writer retirement."""
    graph_path = build_entity_graph(
        tmp_graph.parent.parent,
        [
            _source_entity("observation", "obs1", "r=0.73, p<0.001"),
            _source_entity("observation", "obs2", "fold-change=2.1"),
            _source_entity("proposition", "p1", "X correlates with Y", status="active"),
            _source_entity("proposition", "p2", "X upregulates Y expression", status="active"),
            _source_entity("finding", "f01", "Correlation analysis"),
            _source_entity("finding", "f02", "Differential expression"),
        ],
    )
    assert graph_path == tmp_graph

    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    # Story/paper composition writers retired in Phase 3b; see source-authored story and falsification coverage.
    assert (PROJECT_NS["finding/f01"], RDF.type, SCI_NS.Finding) in knowledge
    assert (PROJECT_NS["proposition/p1"], RDF.type, SCI_NS.Proposition) in knowledge
    assert (PROJECT_NS["observation/obs1"], RDF.type, SCI_NS.Observation) in knowledge
