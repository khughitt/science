from pathlib import Path

from rdflib import RDF, Dataset, Literal, URIRef

from science_tool.graph.belief_snapshot import (
    append_snapshots,
    read_snapshots,
    snapshot_records,
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


def test_snapshot_single_row_persists_authored_capped():
    k, p = _graphs()
    row = snapshot_records(k, p, scalar_enabled=False, as_of="2026-05-24")[0]
    assert row["is_bundle"] is False
    assert row["authored_capped"] is False  # empirical support -> ceiling never fires


def test_with_policy_defaults_backfills_authored_capped():
    from science_tool.graph.belief_snapshot import _with_policy_defaults

    legacy = {"as_of": "x", "claim": "c", "belief_state": "fragile"}  # pre-Slice-B row
    out = _with_policy_defaults(legacy)
    assert out["authored_capped"] is False
    # Slice-A policy identity still backfilled too.
    assert out["policy_id"] == "core-default"
    assert out["policy_version"] == "1"


def test_existing_authored_capped_is_preserved():
    from science_tool.graph.belief_snapshot import _with_policy_defaults

    row = {"as_of": "x", "claim": "c", "policy_id": "p", "policy_version": "2",
           "authored_capped": True}
    out = _with_policy_defaults(row)
    assert out["authored_capped"] is True
