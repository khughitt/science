# science/tests/test_bundle_belief_snapshot.py
from __future__ import annotations

from rdflib import Graph, Literal, RDF, URIRef

from science_tool.graph.belief import EVIDENCE_LINE_CLASS
from science_tool.graph.belief_snapshot import snapshot_records
from science_tool.graph.io import CITO_NS, SCI_NS

MECH = URIRef("http://example.org/science/entity/mechanism/m1")
PA = URIRef("http://example.org/science/entity/proposition/pa")
PB = URIRef("http://example.org/science/entity/proposition/pb")


def _strong(k, prov, target, gid):
    line = URIRef(f"http://example.org/science/entity/evidence-line/{gid}")
    k.add((line, RDF.type, EVIDENCE_LINE_CLASS))
    k.add((line, CITO_NS.supports, target))
    for pred, val in [
        (SCI_NS.evidenceStrength, "strong"), (SCI_NS.evidenceRole, "direct_test"),
        (SCI_NS.evidenceType, "empirical_data_evidence"), (SCI_NS.independenceGroup, gid),
        (SCI_NS.evidenceIndependence, "independent"),
    ]:
        prov.add((line, pred, Literal(val)))


def test_snapshot_emits_mechanism_bundle_row():
    k, prov = Graph(), Graph()
    k.add((MECH, RDF.type, SCI_NS.Mechanism))
    for p in (PA, PB):
        k.add((p, RDF.type, SCI_NS.Proposition))
        k.add((MECH, SCI_NS.hasProposition, p))
    _strong(k, prov, PA, "g1")
    _strong(k, prov, PA, "g2")
    _strong(k, prov, PB, "g3")
    rows = snapshot_records(k, prov, scalar_enabled=False, as_of="2026-06-11")
    mech_rows = [r for r in rows if r["claim"] == str(MECH)]
    assert len(mech_rows) == 1
    row = mech_rows[0]
    assert row["is_bundle"] is True
    assert row["composition_rule"] == "all_steps"
    assert "bottleneck_members" in row
    assert "capped_by_refutation" in row
    # _key()/append_snapshots contract (belief_snapshot.py:72): bundle rows MUST carry
    # input_hashes + scalar_enabled or append raises KeyError.
    from science_tool.graph.belief_snapshot import _key
    assert row["input_hashes"]            # non-empty member-evidence + structure hashes
    assert row["scalar_enabled"] is False
    _key(row)                             # must not raise


def test_snapshot_bundle_rows_are_appendable(tmp_path):
    from science_tool.graph.belief_snapshot import append_snapshots
    k, prov = Graph(), Graph()
    k.add((MECH, RDF.type, SCI_NS.Mechanism))
    k.add((PA, RDF.type, SCI_NS.Proposition))
    k.add((MECH, SCI_NS.hasProposition, PA))
    _strong(k, prov, PA, "g1")
    rows = snapshot_records(k, prov, scalar_enabled=False, as_of="2026-06-11")
    path = tmp_path / "snapshots.jsonl"
    assert append_snapshots(path, rows) == len(rows)   # no KeyError; all rows written
    assert append_snapshots(path, rows) == 0           # idempotent: same key dedupes


def test_snapshot_bundle_row_persists_authored_capped():
    k, prov = Graph(), Graph()
    k.add((MECH, RDF.type, SCI_NS.Mechanism))
    for p in (PA, PB):
        k.add((p, RDF.type, SCI_NS.Proposition))
        k.add((MECH, SCI_NS.hasProposition, p))
    _strong(k, prov, PA, "g1")
    _strong(k, prov, PA, "g2")
    _strong(k, prov, PB, "g3")
    rows = snapshot_records(k, prov, scalar_enabled=False, as_of="2026-06-11")
    row = next(r for r in rows if r["is_bundle"])
    assert row["authored_capped"] is False  # strong empirical members -> ceiling never fires
