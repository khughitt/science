from pathlib import Path

import pytest
from rdflib import Dataset, Graph, Literal, RDF, URIRef

from science_tool.graph.grounding import (
    DEFAULT_GROUNDING_FLOOR,
    GroundingError,
    GroundingStatus,
    ground_proposition,
    ground_propositions,
    load_grounding_graphs,
)
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.store import _graph_uri

TARGET = PROJECT_NS["proposition/p"]
LINE_A = PROJECT_NS["evidence-line/a"]
LINE_B = PROJECT_NS["evidence-line/b"]
LINE_DISPUTE = PROJECT_NS["evidence-line/dispute"]


def _graphs() -> tuple[Graph, Graph]:
    dataset = Dataset()
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    knowledge.add((TARGET, RDF.type, SCI_NS.Proposition))
    return knowledge, provenance


def _support(
    knowledge: Graph,
    provenance: Graph,
    line: URIRef,
    *,
    predicate: URIRef = CITO_NS.supports,
    strength: str = "strong",
    independence: str = "independent",
    group: str = "g1",
    role: str = "direct_test",
    evidence_type: str = "empirical_data_evidence",
) -> None:
    knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
    knowledge.add((line, predicate, TARGET))
    provenance.add((line, SCI_NS.evidenceStrength, Literal(strength)))
    provenance.add((line, SCI_NS.evidenceIndependence, Literal(independence)))
    provenance.add((line, SCI_NS.independenceGroup, Literal(group)))
    provenance.add((line, SCI_NS.evidenceRole, Literal(role)))
    provenance.add((line, SCI_NS.evidenceType, Literal(evidence_type)))


def test_no_evidence_is_unbacked_with_default_policy_and_floor():
    knowledge, provenance = _graphs()

    result = ground_proposition("proposition:p", knowledge, provenance)

    assert result.target_ref == "proposition:p"
    assert result.status == GroundingStatus.UNBACKED
    assert result.belief_magnitude == "speculative"
    assert result.belief_display == "speculative"
    assert result.floor == DEFAULT_GROUNDING_FLOOR == "supported"
    assert result.support_units == 0
    assert result.dispute_units == 0
    assert result.diagnostic_units == 0
    assert result.excluded_units == 0
    assert result.flagged_ungrouped_units == 0
    assert result.contested is False
    assert result.capped_by_refutation is False
    assert result.authored_capped is False
    assert result.qa_dataset_capped is False
    assert result.policy_id == "core-default"
    assert result.policy_version == "1"


def test_one_direct_support_is_below_default_floor():
    knowledge, provenance = _graphs()
    _support(knowledge, provenance, LINE_A)

    result = ground_proposition(TARGET, knowledge, provenance)

    assert result.status == GroundingStatus.BELOW_FLOOR
    assert result.belief_magnitude == "fragile"
    assert result.support_units == 1
    assert result.to_json()["status"] == "below_floor"


def test_two_proxy_supports_in_independent_groups_are_grounded():
    knowledge, provenance = _graphs()
    _support(knowledge, provenance, LINE_A, group="g1", role="proxy")
    _support(knowledge, provenance, LINE_B, group="g2", role="proxy")

    result = ground_proposition("proposition:p", knowledge, provenance)

    assert result.status == GroundingStatus.GROUNDED
    assert result.belief_magnitude == "supported"
    assert result.support_units == 2


def test_model_criticism_generalization_dispute_is_contested_and_diagnostic():
    knowledge, provenance = _graphs()
    _support(knowledge, provenance, LINE_A)
    _support(knowledge, provenance, LINE_B, group="g2")
    _support(
        knowledge,
        provenance,
        LINE_DISPUTE,
        predicate=CITO_NS.disputes,
        group="g3",
        role="model_criticism",
    )
    provenance.add((LINE_DISPUTE, SCI_NS.disputeScope, Literal("generalization")))

    result = ground_proposition("proposition:p", knowledge, provenance)

    assert result.status == GroundingStatus.GROUNDED
    assert result.belief_display.endswith(" (contested)")
    assert result.contested is True
    assert result.dispute_units == 0
    assert result.diagnostic_units == 1


def test_invalid_floor_raises_grounding_error():
    knowledge, provenance = _graphs()

    with pytest.raises(GroundingError, match="unknown grounding floor"):
        ground_proposition("proposition:p", knowledge, provenance, floor="certain")


def test_missing_proposition_target_raises_grounding_error():
    knowledge, provenance = _graphs()

    with pytest.raises(GroundingError, match="not found in knowledge graph"):
        ground_proposition("proposition:missing", knowledge, provenance)


def test_proposition_ref_slug_is_case_insensitive():
    knowledge, provenance = _graphs()

    result = ground_proposition("proposition:P", knowledge, provenance)

    assert result.target_ref == "proposition:p"


def test_ground_propositions_returns_one_item_list():
    knowledge, provenance = _graphs()

    results = ground_propositions(["proposition:p"], knowledge, provenance)

    assert len(results) == 1
    assert results[0].target_ref == "proposition:p"


def test_load_grounding_graphs_reads_named_knowledge_and_provenance(tmp_path: Path):
    dataset = Dataset()
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    knowledge.add((TARGET, RDF.type, SCI_NS.Proposition))
    provenance.add((LINE_A, SCI_NS.evidenceStrength, Literal("strong")))
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir()
    dataset.serialize(destination=str(graph_path), format="trig")

    loaded_knowledge, loaded_provenance = load_grounding_graphs(graph_path)

    assert (TARGET, RDF.type, SCI_NS.Proposition) in loaded_knowledge
    assert (LINE_A, SCI_NS.evidenceStrength, Literal("strong")) in loaded_provenance
