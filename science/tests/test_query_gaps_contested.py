from pathlib import Path

from rdflib import Dataset, Literal, RDF, URIRef

from science_tool.graph.io import CITO_NS, SCHEMA_NS, SCI_NS
from science_tool.graph.store import _graph_uri, query_gaps

# Claim whose only dispute is circular: count-based logic would flag contested; belief does not.
CIRC = URIRef("https://example.org/prop/circular")
CIRC_SUP = URIRef("https://example.org/el/circ-sup")
CIRC_DIS = URIRef("https://example.org/el/circ-dispute")

# Claim with a genuine independent dispute: belief flags contested.
REAL = URIRef("https://example.org/prop/real")
REAL_SUP = URIRef("https://example.org/el/real-sup")
REAL_DIS = URIRef("https://example.org/el/real-dispute")


def _support_line(k, p, line: URIRef, claim: URIRef, group: str) -> None:
    k.add((line, RDF.type, SCI_NS.EvidenceLine))
    k.add((line, CITO_NS.supports, claim))
    p.add((line, SCI_NS.evidenceStrength, Literal("strong")))
    p.add((line, SCI_NS.evidenceIndependence, Literal("independent")))
    p.add((line, SCI_NS.independenceGroup, Literal(group)))
    p.add((line, SCI_NS.evidenceRole, Literal("direct_test")))
    p.add((line, SCI_NS.evidenceType, Literal("empirical_data_evidence")))


def _write_graph(tmp_path: Path) -> Path:
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))

    k.add((CIRC, RDF.type, SCI_NS.Proposition))
    k.add((CIRC, SCHEMA_NS.text, Literal("circular-dispute claim")))
    _support_line(k, p, CIRC_SUP, CIRC, "g1")
    # circular dispute in the support's own group: reduction excludes it, so not contested
    k.add((CIRC_DIS, RDF.type, SCI_NS.EvidenceLine))
    k.add((CIRC_DIS, CITO_NS.disputes, CIRC))
    p.add((CIRC_DIS, SCI_NS.evidenceIndependence, Literal("circular")))
    p.add((CIRC_DIS, SCI_NS.independenceGroup, Literal("g1")))

    k.add((REAL, RDF.type, SCI_NS.Proposition))
    k.add((REAL, SCHEMA_NS.text, Literal("genuinely contested claim")))
    _support_line(k, p, REAL_SUP, REAL, "g2")
    # independent dispute in its own group survives reduction → contested
    k.add((REAL_DIS, RDF.type, SCI_NS.EvidenceLine))
    k.add((REAL_DIS, CITO_NS.disputes, REAL))
    p.add((REAL_DIS, SCI_NS.evidenceStrength, Literal("strong")))
    p.add((REAL_DIS, SCI_NS.evidenceIndependence, Literal("independent")))
    p.add((REAL_DIS, SCI_NS.independenceGroup, Literal("g3")))

    out = tmp_path / "graph.trig"
    ds.serialize(destination=str(out), format="trig")
    return out


def test_gaps_contested_is_belief_derived_not_count_based(tmp_path: Path):
    graph_path = _write_graph(tmp_path)

    # Circular dispute: support_count>0 and dispute_count>0 under the old rule, but belief
    # excludes the circular line, so query_gaps must NOT flag contested.
    circ_rows = query_gaps(graph_path=graph_path, center=str(CIRC), hops=1, limit=50)
    circ_row = next((r for r in circ_rows if r["entity"] == str(CIRC)), None)
    if circ_row is not None:
        assert "evidential_fragility(contested)" not in circ_row["issues"]

    # Independent dispute: belief keeps it, so query_gaps flags contested.
    real_rows = query_gaps(graph_path=graph_path, center=str(REAL), hops=1, limit=50)
    real_row = next(r for r in real_rows if r["entity"] == str(REAL))
    assert "evidential_fragility(contested)" in real_row["issues"]
