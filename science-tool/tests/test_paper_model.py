from pathlib import Path

import pytest
from rdflib.namespace import RDF

from science_tool.graph.store import (
    SCI_NS,
    PROJECT_NS,
    _graph_uri,
    _load_dataset,
    add_finding,
    add_hypothesis,
    add_interpretation,
    add_observation,
    add_paper_entity,
    add_proposition,
    add_story,
    init_graph_file,
)


@pytest.fixture()
def tmp_graph(tmp_path: Path) -> Path:
    graph_path = tmp_path / "knowledge" / "graph.trig"
    init_graph_file(graph_path)
    return graph_path


def test_add_finding(tmp_graph: Path) -> None:
    add_proposition(tmp_graph, text="X correlates with Y", source="paper:a", proposition_id="p1")
    add_observation(tmp_graph, description="r=0.73", data_source="data-package:results", observation_id="obs1")
    finding_uri = add_finding(
        tmp_graph,
        summary="Analysis shows X-Y correlation",
        confidence="moderate",
        propositions=["proposition:p1"],
        observations=["observation:obs1"],
        source="data-package:results",
        finding_id="f01",
    )
    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    assert (finding_uri, RDF.type, SCI_NS.Finding) in knowledge
    assert (finding_uri, SCI_NS.contains, PROJECT_NS["proposition/p1"]) in knowledge
    assert (finding_uri, SCI_NS.contains, PROJECT_NS["observation/obs1"]) in knowledge
    assert (finding_uri, SCI_NS.groundedBy, PROJECT_NS["data-package/results"]) in knowledge


def test_add_finding_invalid_confidence(tmp_graph: Path) -> None:
    with pytest.raises(Exception):
        add_finding(tmp_graph, "summary", "invalid", ["p:1"], ["o:1"], "dp:1")


def test_add_interpretation(tmp_graph: Path) -> None:
    add_proposition(tmp_graph, text="X causes Y", source="paper:a", proposition_id="p1")
    add_observation(tmp_graph, description="r=0.73", data_source="data-package:x", observation_id="obs1")
    add_finding(
        tmp_graph,
        "Correlation found",
        "moderate",
        ["proposition:p1"],
        ["observation:obs1"],
        "data-package:x",
        "f01",
    )
    interp_uri = add_interpretation(
        tmp_graph,
        summary="Initial expression analysis suggests X-Y link",
        findings=["finding:f01"],
        context="Exploratory analysis of dataset X",
        interpretation_id="interp-01",
    )
    dataset = _load_dataset(tmp_graph)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    assert (interp_uri, RDF.type, SCI_NS.Interpretation) in knowledge
    assert (interp_uri, SCI_NS.contains, PROJECT_NS["finding/f01"]) in knowledge


def test_add_story(tmp_graph: Path) -> None:
    add_hypothesis(tmp_graph, "h01", "X regulates Y", "paper:smith-2024")
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
    # Atoms
    add_hypothesis(tmp_graph, "h01", "X regulates Y", "paper:smith-2024")
    obs_uri1 = add_observation(tmp_graph, "r=0.73, p<0.001", "data-package:expr", observation_id="obs1")
    add_observation(tmp_graph, "fold-change=2.1", "data-package:expr", observation_id="obs2")
    prop_uri1 = add_proposition(tmp_graph, "X correlates with Y", "paper:smith-2024", proposition_id="p1")
    add_proposition(tmp_graph, "X upregulates Y expression", "data-package:expr", proposition_id="p2")

    # Findings
    finding_uri1 = add_finding(
        tmp_graph,
        "Correlation analysis",
        "moderate",
        ["proposition:p1"],
        ["observation:obs1"],
        "data-package:expr",
        "f01",
    )
    add_finding(
        tmp_graph,
        "Differential expression",
        "high",
        ["proposition:p2"],
        ["observation:obs2"],
        "data-package:expr",
        "f02",
    )

    # Interpretation
    interp_uri = add_interpretation(
        tmp_graph,
        "Expression analysis suggests X-Y regulation",
        ["finding:f01", "finding:f02"],
        context="Initial exploratory analysis",
        interpretation_id="interp01",
    )

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
    assert (interp_uri, SCI_NS.contains, finding_uri1) in knowledge
    assert (finding_uri1, SCI_NS.contains, prop_uri1) in knowledge
    assert (finding_uri1, SCI_NS.contains, obs_uri1) in knowledge
    assert (finding_uri1, SCI_NS.groundedBy, PROJECT_NS["data-package/expr"]) in knowledge
