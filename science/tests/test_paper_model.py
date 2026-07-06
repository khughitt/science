from pathlib import Path

import pytest
from rdflib.namespace import RDF

from conftest import build_entity_graph
from science_tool.graph.store import (
    PROJECT_NS,
    SCI_NS,
    _graph_uri,
    _load_dataset,
    add_paper_entity,
    add_story,
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


def test_add_story(tmp_graph: Path) -> None:
    graph_path = build_entity_graph(
        tmp_graph.parent.parent,
        [_source_entity("hypothesis", "h01", "X regulates Y", status="proposed")],
    )
    assert graph_path == tmp_graph
    story_uri = add_story(
        tmp_graph,
        title="X regulates Y through pathway Z",
        summary="Evidence from multiple analyses",
        about="hypothesis:h01",
        interpretations=["interpretation:interp-01"],
        status="developing",
        story_id="s01",
    )
    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    assert (story_uri, RDF.type, SCI_NS.Story) in knowledge
    assert (story_uri, SCI_NS.synthesizes, PROJECT_NS["interpretation/interp-01"]) in knowledge
    assert (story_uri, SCI_NS.organizedBy, PROJECT_NS["hypothesis/h01"]) in knowledge


def test_add_story_invalid_status(tmp_graph: Path) -> None:
    with pytest.raises(Exception):
        add_story(tmp_graph, "title", "summary", "hypothesis:h01", [], status="invalid")


def test_add_paper_entity(tmp_graph: Path) -> None:
    paper_uri = add_paper_entity(
        tmp_graph,
        title="The Role of X in Y Regulation",
        stories=["story:s01"],
        status="outline",
        paper_id="paper-01",
    )
    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    assert (paper_uri, RDF.type, SCI_NS.Paper) in knowledge
    assert (paper_uri, SCI_NS.comprises, PROJECT_NS["story/s01"]) in knowledge


def test_add_paper_entity_invalid_status(tmp_graph: Path) -> None:
    with pytest.raises(Exception):
        add_paper_entity(tmp_graph, "title", ["story:s01"], status="invalid")


def test_full_composition_chain(tmp_graph: Path) -> None:
    """Test: observation -> proposition -> finding -> interpretation -> story -> paper."""
    graph_path = build_entity_graph(
        tmp_graph.parent.parent,
        [
            _source_entity("hypothesis", "h01", "X regulates Y", status="proposed"),
            _source_entity("observation", "obs1", "r=0.73, p<0.001"),
            _source_entity("observation", "obs2", "fold-change=2.1"),
            _source_entity("proposition", "p1", "X correlates with Y", status="active"),
            _source_entity("proposition", "p2", "X upregulates Y expression", status="active"),
            _source_entity("finding", "f01", "Correlation analysis"),
            _source_entity("finding", "f02", "Differential expression"),
            _source_entity("interpretation", "interp01", "Expression analysis suggests X-Y regulation"),
        ],
    )
    assert graph_path == tmp_graph
    interp_uri = PROJECT_NS["interpretation/interp01"]

    # Story
    story_uri = add_story(
        tmp_graph,
        "X regulates Y",
        "Multiple lines of evidence for X-Y regulation",
        "hypothesis:h01",
        ["interpretation:interp01"],
        status="developing",
        story_id="s01",
    )

    # Paper
    paper_uri = add_paper_entity(
        tmp_graph,
        "The Role of X in Y Regulation",
        ["story:s01"],
        status="outline",
        paper_id="paper01",
    )

    # Verify full chain using returned URIRefs to avoid slug-transformation ambiguity
    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    assert (paper_uri, SCI_NS.comprises, story_uri) in knowledge
    assert (story_uri, SCI_NS.synthesizes, interp_uri) in knowledge
    assert (story_uri, SCI_NS.organizedBy, PROJECT_NS["hypothesis/h01"]) in knowledge
    assert (PROJECT_NS["finding/f01"], RDF.type, SCI_NS.Finding) in knowledge
    assert (PROJECT_NS["proposition/p1"], RDF.type, SCI_NS.Proposition) in knowledge
    assert (PROJECT_NS["observation/obs1"], RDF.type, SCI_NS.Observation) in knowledge
