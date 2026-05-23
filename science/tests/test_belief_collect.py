from rdflib import Graph, URIRef, Literal, RDF
from rdflib.namespace import PROV
from science_tool.graph.io import SCI_NS, CITO_NS
from science_tool.graph.belief import collect_evidence_units, EVIDENCE_LINE_CLASS

CLAIM = URIRef("http://example.org/science/entity/proposition/p")
HYP = URIRef("http://example.org/science/entity/hypothesis/h")
LINE = URIRef("http://example.org/science/entity/evidence-line/e")
PAPER = URIRef("http://example.org/science/entity/paper/x")
BARE = URIRef("http://example.org/science/entity/observation/o")

def test_collects_line_metadata_from_provenance():
    knowledge, provenance = Graph(), Graph()
    knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
    knowledge.add((LINE, CITO_NS.disputes, CLAIM))
    knowledge.add((BARE, CITO_NS.supports, CLAIM))            # not a line -> ignored
    provenance.add((LINE, SCI_NS.evidenceStrength, Literal("strong")))
    provenance.add((LINE, SCI_NS.evidenceIndependence, Literal("independent")))
    provenance.add((LINE, SCI_NS.independenceGroup, Literal("g1")))
    provenance.add((LINE, SCI_NS.evidenceRole, Literal("model_criticism")))
    provenance.add((LINE, SCI_NS.disputeScope, Literal("generalization")))
    provenance.add((LINE, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    units = collect_evidence_units(knowledge, provenance, [CLAIM])
    assert len(units) == 1
    u = units[0]
    assert u.stance == "disputes" and u.strength == "strong" and u.independence == "independent"
    assert u.independence_group == "g1" and u.evidence_role == "model_criticism"
    assert u.dispute_scope == "generalization" and u.evidence_type == "empirical_data_evidence"


def test_reads_measurement_model_proxy_source_and_observability():
    """has_measurement_model presence-check, proxy_directness, source, and shared_* keys round-trip."""
    knowledge, provenance = Graph(), Graph()
    knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
    knowledge.add((LINE, CITO_NS.supports, CLAIM))
    provenance.add((LINE, SCI_NS.measurementModel, Literal("logistic-growth")))
    provenance.add((LINE, SCI_NS.proxyDirectness, Literal("indirect")))
    provenance.add((LINE, PROV.wasDerivedFrom, PAPER))
    provenance.add((LINE, SCI_NS.sharedDataset, Literal("ds:alpha")))
    provenance.add((LINE, SCI_NS.sharedPlatform, Literal("scRNA")))
    (u,) = collect_evidence_units(knowledge, provenance, [CLAIM])
    assert u.has_measurement_model is True
    assert u.proxy_directness == "indirect"
    assert u.source == str(PAPER)
    assert set(u.observability_keys) == {"shared_dataset", "shared_platform"}


def test_line_on_multiple_targets_counted_once():
    """A line bearing on both a claim and a hypothesis is de-duped by URI (counted once)."""
    knowledge, provenance = Graph(), Graph()
    knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
    knowledge.add((LINE, CITO_NS.supports, CLAIM))
    knowledge.add((LINE, CITO_NS.supports, HYP))
    units = collect_evidence_units(knowledge, provenance, [CLAIM, HYP])
    assert [u.line_uri for u in units] == [str(LINE)]
