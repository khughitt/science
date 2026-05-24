from pathlib import Path

from rdflib import Dataset, Literal, RDF, URIRef

from science_tool.graph.io import CITO_NS, SCHEMA_NS, SCI_NS
from science_tool.graph.store import _graph_uri, query_uncertainty

PROP = URIRef("https://example.org/prop/p1")
SUP = URIRef("https://example.org/el/sup")
DIS = URIRef("https://example.org/el/circular-dispute")


def _write_graph(tmp_path: Path) -> Path:
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))
    k.add((PROP, RDF.type, SCI_NS.Proposition))
    k.add((PROP, SCHEMA_NS.text, Literal("claim text")))
    p.add((PROP, SCI_NS.epistemicStatus, Literal("disputed")))
    # one support line
    k.add((SUP, RDF.type, SCI_NS.EvidenceLine))
    k.add((SUP, CITO_NS.supports, PROP))
    p.add((SUP, SCI_NS.evidenceStrength, Literal("strong")))
    p.add((SUP, SCI_NS.evidenceIndependence, Literal("independent")))
    p.add((SUP, SCI_NS.independenceGroup, Literal("g1")))
    p.add((SUP, SCI_NS.evidenceRole, Literal("direct_test")))
    p.add((SUP, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    # one CIRCULAR dispute line: count-based logic would mark contested; belief excludes it
    k.add((DIS, RDF.type, SCI_NS.EvidenceLine))
    k.add((DIS, CITO_NS.disputes, PROP))
    p.add((DIS, SCI_NS.evidenceIndependence, Literal("circular")))
    p.add((DIS, SCI_NS.independenceGroup, Literal("g1")))
    out = tmp_path / "graph.trig"
    ds.serialize(destination=str(out), format="trig")
    return out


def test_contested_signal_is_belief_derived_not_count_based(tmp_path: Path):
    graph_path = _write_graph(tmp_path)
    rows = query_uncertainty(graph_path=graph_path, top=10)
    row = next(r for r in rows if r["entity"] == str(PROP))
    # A circular dispute must NOT make the claim contested (belief excludes circular lines),
    # even though support_count>0 and dispute_count>0 under the old count-based rule.
    assert "contested" not in row["signals"]
