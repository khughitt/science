from pathlib import Path

from rdflib import Dataset, Literal, RDF, URIRef

from science_tool.graph.belief_snapshot import (
    append_snapshots, read_snapshots, snapshot_records,
)
from science_tool.graph.io import CITO_NS, SCI_NS
from science_tool.graph.store import _graph_uri

PROP = URIRef("https://example.org/prop/p1")
LINE = URIRef("https://example.org/el/yang")
EVIDENCE_LINE_CLASS = SCI_NS.EvidenceLine


def _graphs():
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))
    k.add((PROP, RDF.type, SCI_NS.Proposition))
    k.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
    k.add((LINE, CITO_NS.supports, PROP))
    p.add((LINE, SCI_NS.evidenceStrength, Literal("strong")))
    p.add((LINE, SCI_NS.evidenceIndependence, Literal("independent")))
    p.add((LINE, SCI_NS.independenceGroup, Literal("g1")))
    p.add((LINE, SCI_NS.evidenceRole, Literal("direct_test")))
    p.add((LINE, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    return k, p


def test_snapshot_records_basic_shape():
    k, p = _graphs()
    rows = snapshot_records(k, p, scalar_enabled=False, as_of="2026-05-24")
    assert len(rows) == 1
    row = rows[0]
    assert row["claim"] == str(PROP)
    assert row["belief_state"] == "fragile"
    assert row["scalar_enabled"] is False
    assert row["net_band"] is None                 # scalar fields null when disabled
    assert row["massed_support_score"] is None
    assert row["input_hashes"] and all(h.startswith("sha256:") for h in row["input_hashes"])
    assert row["config_version"] == "belief-logodds-v3"


def test_snapshot_records_scalar_enabled_fills_scores():
    k, p = _graphs()
    row = snapshot_records(k, p, scalar_enabled=True, as_of="2026-05-24")[0]
    assert row["scalar_enabled"] is True
    assert row["massed_support_score"] == 7
    assert row["net_band"] is not None


def test_append_is_idempotent_then_grows_on_change(tmp_path: Path):
    k, p = _graphs()
    out = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    rows = snapshot_records(k, p, scalar_enabled=False, as_of="2026-05-24")
    assert append_snapshots(out, rows) == 1
    assert append_snapshots(out, rows) == 0          # idempotent no-op
    # Same day, opt-in toggled -> distinct scalar_enabled key -> new row
    rows_on = snapshot_records(k, p, scalar_enabled=True, as_of="2026-05-24")
    assert append_snapshots(out, rows_on) == 1
    stored = read_snapshots(out)
    assert len(stored) == 2
    assert {r["scalar_enabled"] for r in stored} == {True, False}
