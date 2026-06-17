import json
from pathlib import Path

import pytest
from rdflib import Graph, Literal, RDF, URIRef

from science_tool.graph.dataset_qa import DatasetQaReportError, emit_dataset_qa_layer
from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.io import CITO_NS, SCI_NS


class _Ent:
    def __init__(self, canonical_id, kind="dataset", qa_report=""):
        self.canonical_id = canonical_id
        self.kind = kind
        self.qa_report = qa_report


class _Sources:
    def __init__(self, project_root, entities):
        self.project_root = str(project_root)
        self.entities = entities


def _write_report(path: Path, *, failed: bool, fail_resources=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "package": "p", "package_structural_failed": failed,
        "resources": [{"resource": r, "status": "fail"} for r in fail_resources],
    }))


def _empirical_line(k, p, line, target, dataset, role="analyzed", etype="empirical_data_evidence"):
    k.add((line, RDF.type, SCI_NS.EvidenceLine))
    k.add((line, CITO_NS.supports, target))
    p.add((line, SCI_NS.evidenceType, Literal(etype)))
    usage = URIRef(str(line) + "/usage")
    p.add((line, SCI_NS.hasDatasetUsage, usage))
    p.add((usage, RDF.type, SCI_NS.DatasetUsage))
    p.add((usage, SCI_NS.dataset, dataset))
    p.add((usage, SCI_NS.usageRole, Literal(role)))
    p.add((usage, SCI_NS.usageOverlap, Literal("full")))


def test_failed_report_stamps_dataset_and_empirical_line(tmp_path):
    _write_report(tmp_path / "qa" / "bad" / "qa_report.json", failed=True, fail_resources=["t1"])
    ds_uri = project_entity_uri("dataset:bad")
    k, p = Graph(), Graph()
    line = URIRef("https://example.org/p/evidence-line/ev1")
    target = URIRef("https://example.org/p/proposition/c1")
    _empirical_line(k, p, line, target, ds_uri)   # dataset URI must match project_entity_uri
    sources = _Sources(tmp_path, [_Ent("dataset:bad", qa_report="qa/bad/qa_report.json")])

    emit_dataset_qa_layer(k, p, sources)

    assert (ds_uri, SCI_NS.qaStructuralFailed, Literal(True)) in p
    assert (ds_uri, SCI_NS.qaFailedResource, Literal("t1")) in p
    assert (line, SCI_NS.qaFailedDataset, ds_uri) in p


def test_clean_report_stamps_verdict_but_no_line_flag(tmp_path):
    _write_report(tmp_path / "qa" / "ok" / "qa_report.json", failed=False)
    ds_uri = project_entity_uri("dataset:ok")
    k, p = Graph(), Graph()
    line = URIRef("https://example.org/p/evidence-line/ev2")
    _empirical_line(k, p, line, URIRef("https://example.org/p/proposition/c2"), ds_uri)
    sources = _Sources(tmp_path, [_Ent("dataset:ok", qa_report="qa/ok/qa_report.json")])

    emit_dataset_qa_layer(k, p, sources)
    assert (ds_uri, SCI_NS.qaStructuralFailed, Literal(False)) in p
    assert len(list(p.triples((line, SCI_NS.qaFailedDataset, None)))) == 0


def test_non_empirical_line_not_stamped(tmp_path):
    _write_report(tmp_path / "qa" / "bad" / "qa_report.json", failed=True)
    ds_uri = project_entity_uri("dataset:bad")
    k, p = Graph(), Graph()
    line = URIRef("https://example.org/p/evidence-line/ev3")
    _empirical_line(k, p, line, URIRef("https://example.org/p/proposition/c3"), ds_uri,
                    etype="simulation_evidence")
    sources = _Sources(tmp_path, [_Ent("dataset:bad", qa_report="qa/bad/qa_report.json")])
    emit_dataset_qa_layer(k, p, sources)
    assert len(list(p.triples((line, SCI_NS.qaFailedDataset, None)))) == 0


def test_missing_report_raises(tmp_path):
    sources = _Sources(tmp_path, [_Ent("dataset:gone", qa_report="qa/gone/qa_report.json")])
    with pytest.raises(DatasetQaReportError):
        emit_dataset_qa_layer(Graph(), Graph(), sources)


def test_non_boolean_verdict_raises_not_coerced(tmp_path):
    # bool("false") is True — must fail loud, not silently invert the verdict.
    path = tmp_path / "qa" / "weird" / "qa_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"package": "p", "package_structural_failed": "false", "resources": []}))
    sources = _Sources(tmp_path, [_Ent("dataset:weird", qa_report="qa/weird/qa_report.json")])
    with pytest.raises(DatasetQaReportError):
        emit_dataset_qa_layer(Graph(), Graph(), sources)
