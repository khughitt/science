from rdflib import Graph, URIRef, Literal, RDF
from rdflib.namespace import PROV
from science_tool.graph.io import PROJECT_NS, SCI_NS, CITO_NS
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


DATASET = URIRef("http://example.org/science/entity/dataset/d")


def test_reference_source_sets_is_reference_dataset():
    """A line whose source dataset carries sci:sourceClass 'reference' → is_reference_dataset True."""
    knowledge, provenance = Graph(), Graph()
    knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
    knowledge.add((LINE, CITO_NS.supports, CLAIM))
    knowledge.add((DATASET, SCI_NS.sourceClass, Literal("reference")))
    provenance.add((LINE, PROV.wasDerivedFrom, DATASET))
    (u,) = collect_evidence_units(knowledge, provenance, [CLAIM])
    assert u.is_reference_dataset is True


def test_non_reference_source_leaves_flag_false():
    """A line whose source dataset carries sci:sourceClass 'observational' → is_reference_dataset False."""
    knowledge, provenance = Graph(), Graph()
    knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
    knowledge.add((LINE, CITO_NS.supports, CLAIM))
    knowledge.add((DATASET, SCI_NS.sourceClass, Literal("observational")))
    provenance.add((LINE, PROV.wasDerivedFrom, DATASET))
    (u,) = collect_evidence_units(knowledge, provenance, [CLAIM])
    assert u.is_reference_dataset is False


def test_multi_derived_from_detects_reference_dataset():
    """is_reference_dataset True when one of multiple wasDerivedFrom objects is the reference
    dataset URI — proves ALL objects are scanned, not just the first."""
    OTHER = URIRef("http://example.org/files/source.csv")
    knowledge, provenance = Graph(), Graph()
    knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
    knowledge.add((LINE, CITO_NS.supports, CLAIM))
    knowledge.add((DATASET, SCI_NS.sourceClass, Literal("reference")))
    provenance.add((LINE, PROV.wasDerivedFrom, OTHER))   # non-reference, listed first
    provenance.add((LINE, PROV.wasDerivedFrom, DATASET))  # reference dataset
    (u,) = collect_evidence_units(knowledge, provenance, [CLAIM])
    assert u.is_reference_dataset is True


def test_collect_evidence_units_merges_committed_dataset_independence_for_untagged_lines() -> None:
    knowledge = Graph()
    provenance = Graph()
    target = PROJECT_NS["proposition/p1"]
    line_a = PROJECT_NS["evidence-line/a"]
    line_b = PROJECT_NS["evidence-line/b"]
    record = PROJECT_NS["dataset-independence/r1"]
    for line in (line_a, line_b):
        knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
        knowledge.add((line, CITO_NS.supports, target))
    provenance.add((record, RDF.type, SCI_NS.DatasetIndependenceCommitment))
    provenance.add((record, SCI_NS.independenceTarget, target))
    provenance.add((record, SCI_NS.independenceGroup, Literal("dataset-derived:gtex-v8")))
    provenance.add((record, SCI_NS.independenceMember, line_a))
    provenance.add((record, SCI_NS.independenceMember, line_b))

    units = collect_evidence_units(knowledge, provenance, [target])

    assert [(unit.line_uri, unit.independence, unit.independence_group) for unit in units] == [
        (str(line_a), "shared-source", "dataset-derived:gtex-v8"),
        (str(line_b), "shared-source", "dataset-derived:gtex-v8"),
    ]


def test_collect_evidence_units_keeps_authored_circular_over_derived_commitment() -> None:
    knowledge = Graph()
    provenance = Graph()
    target = PROJECT_NS["proposition/p1"]
    line = PROJECT_NS["evidence-line/a"]
    record = PROJECT_NS["dataset-independence/r1"]
    knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
    knowledge.add((line, CITO_NS.supports, target))
    provenance.add((line, SCI_NS.evidenceIndependence, Literal("circular")))
    provenance.add((line, SCI_NS.independenceGroup, Literal("manual-circular")))
    provenance.add((record, RDF.type, SCI_NS.DatasetIndependenceCommitment))
    provenance.add((record, SCI_NS.independenceTarget, target))
    provenance.add((record, SCI_NS.independenceGroup, Literal("dataset-derived:gtex-v8")))
    provenance.add((record, SCI_NS.independenceMember, line))

    units = collect_evidence_units(knowledge, provenance, [target])

    assert units[0].independence == "circular"
    assert units[0].independence_group == "manual-circular"


def test_collect_evidence_units_ignores_dataset_independence_candidates_for_scoring() -> None:
    knowledge = Graph()
    provenance = Graph()
    target = PROJECT_NS["proposition/p1"]
    line_a = PROJECT_NS["evidence-line/a"]
    line_b = PROJECT_NS["evidence-line/b"]
    record = PROJECT_NS["dataset-independence/r1"]
    for line in (line_a, line_b):
        knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
        knowledge.add((line, CITO_NS.supports, target))
    provenance.add((record, RDF.type, SCI_NS.DatasetIndependenceCandidate))
    provenance.add((record, SCI_NS.independenceTarget, target))
    provenance.add((record, SCI_NS.independenceGroup, Literal("dataset-derived:gtex-v8")))
    provenance.add((record, SCI_NS.independenceMember, line_a))
    provenance.add((record, SCI_NS.independenceMember, line_b))

    units = collect_evidence_units(knowledge, provenance, [target])

    assert [(unit.independence, unit.independence_group) for unit in units] == [(None, None), (None, None)]
