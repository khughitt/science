from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from science_model.propositions import PropositionEntity

from science_tool.dag.workbench import WorkbenchRow, _proposition_for_row
from science_tool.graph.io import SCI_NS
from science_tool.graph.materialize import _add_reasoning_metadata


def test_proposition_carries_legacy_provenance():
    p = PropositionEntity(
        id="proposition:x",
        subject="gene:phf19",
        object="outcome:os",
        predicate="associates_with",
        polarity="positive",
        legacy_patch="h1-prognosis",
        legacy_edge_id=8,
    )
    assert p.legacy_patch == "h1-prognosis"
    assert p.legacy_edge_id == 8


def test_workbench_row_legacy_provenance_flows_to_proposition():
    row = WorkbenchRow(
        subject="gene:phf19",
        predicate="associates_with",
        object="outcome:os",
        patch="h1-prognosis",
        polarity="positive",
        legacy_patch="h1-prognosis",
        legacy_edge_id=8,
    )
    prop = _proposition_for_row(row)
    assert prop.legacy_patch == "h1-prognosis"
    assert prop.legacy_edge_id == 8


def test_legacy_provenance_materializes_to_rdf():
    p = PropositionEntity(
        id="proposition:x",
        subject="gene:phf19",
        object="outcome:os",
        predicate="associates_with",
        polarity="positive",
        legacy_patch="h1-prognosis",
        legacy_edge_id=8,
    )
    prov = Graph()
    uri = URIRef("http://example.org/science/entity/proposition/x")
    _add_reasoning_metadata(uri=uri, provenance=prov, entity=p)
    assert (uri, SCI_NS.legacyPatch, Literal("h1-prognosis")) in prov
    assert (uri, SCI_NS.legacyEdgeId, Literal(8)) in prov


def test_legacy_provenance_absent_emits_no_triples():
    p = PropositionEntity(
        id="proposition:x",
        subject="gene:phf19",
        object="outcome:os",
        predicate="associates_with",
        polarity="positive",
    )
    prov = Graph()
    uri = URIRef("http://example.org/science/entity/proposition/x")
    _add_reasoning_metadata(uri=uri, provenance=prov, entity=p)
    preds = {pred for _, pred, _ in prov}
    assert SCI_NS.legacyPatch not in preds
    assert SCI_NS.legacyEdgeId not in preds
