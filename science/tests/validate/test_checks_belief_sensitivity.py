from pathlib import Path

from rdflib import RDF, Dataset, Literal, URIRef

from science_tool.graph.io import CITO_NS, SCI_NS
from science_tool.graph.store import _graph_uri
from science_tool.validate import Severity, ValidateContext


def _manifest(root: Path) -> None:
    root.joinpath("science.yaml").write_text(
        "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\n"
        "status: active\nsummary: d\nprofile: research\nlayout_version: 1\n",
        encoding="utf-8",
    )


def _ctx(root: Path) -> ValidateContext:
    _manifest(root)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _line(p, k, uri, target, **meta):
    k.add((uri, RDF.type, SCI_NS.EvidenceLine))
    k.add((uri, CITO_NS.supports if meta.get("stance", "supports") == "supports" else CITO_NS.disputes, target))
    for pred, val in (
        (SCI_NS.evidenceStrength, meta.get("strength", "strong")),
        (SCI_NS.evidenceIndependence, meta.get("independence", "independent")),
        (SCI_NS.independenceGroup, meta["group"]),
        (SCI_NS.evidenceRole, meta.get("role", "direct_test")),
        (SCI_NS.evidenceType, meta.get("etype", "empirical_data_evidence")),
    ):
        p.add((uri, pred, Literal(val)))


def _write_two_support_graph(root: Path) -> None:
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))
    prop = URIRef("https://example.org/prop/p1")
    k.add((prop, RDF.type, SCI_NS.Proposition))
    # exactly two independent direct-test supports -> well_supported; drop one -> fragile (flips)
    _line(p, k, URIRef("https://example.org/el/a"), prop, group="g1")
    _line(p, k, URIRef("https://example.org/el/b"), prop, group="g2")
    (root / "knowledge").mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(root / "knowledge" / "graph.trig"), format="trig")


def _write_support_plus_diagnostic_graph(root: Path) -> None:
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))
    prop = URIRef("https://example.org/prop/p2")
    k.add((prop, RDF.type, SCI_NS.Proposition))
    _line(p, k, URIRef("https://example.org/el/sup"), prop, group="g1")
    _line(p, k, URIRef("https://example.org/el/crit"), prop, group="g2",
          stance="disputes", role="model_criticism")
    (root / "knowledge").mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(root / "knowledge" / "graph.trig"), format="trig")


def _write_one_support_plus_excluded_circular_graph(root: Path) -> None:
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    p = ds.graph(_graph_uri("graph/provenance"))
    prop = URIRef("https://example.org/prop/p3")
    k.add((prop, RDF.type, SCI_NS.Proposition))
    _line(p, k, URIRef("https://example.org/el/sup"), prop, group="g1")
    _line(p, k, URIRef("https://example.org/el/circular"), prop, group="g2",
          stance="disputes", independence="circular")
    (root / "knowledge").mkdir(parents=True, exist_ok=True)
    ds.serialize(destination=str(root / "knowledge" / "graph.trig"), format="trig")


def test_fragile_single_line_flags_when_drop_flips(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_belief_fragile_single_line
    _write_two_support_graph(tmp_path)
    results = list(check_belief_fragile_single_line(_ctx(tmp_path)))
    assert any(r.severity is Severity.WARN for r in results)


def test_fragile_single_line_flags_diagnostic_only_contestation(tmp_path: Path):
    # h012 shape: one support + one model_criticism dispute. Dropping the diagnostic flips
    # contested True->False; dropping the support flips magnitude. Either way it is fragile.
    from science_tool.validate.checks.evidence_lines import check_belief_fragile_single_line
    _write_support_plus_diagnostic_graph(tmp_path)
    results = list(check_belief_fragile_single_line(_ctx(tmp_path)))
    assert any(r.severity is Severity.WARN for r in results)


def test_fragile_single_line_skips_single_kept_unit_plus_excluded_circular(tmp_path: Path):
    # Raw units has length 2, but only one line is effectively kept. Leave-one-out operates on
    # kept units, so this should not warn.
    from science_tool.validate.checks.evidence_lines import check_belief_fragile_single_line
    _write_one_support_plus_excluded_circular_graph(tmp_path)
    assert list(check_belief_fragile_single_line(_ctx(tmp_path))) == []


def test_nonreproducible_errors_when_stored_belief_mismatches(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    # Snapshot the current (correct) belief, then corrupt the stored belief_state.
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    corrupted = rows[0] | {"belief_state": "speculative"}      # same input_hashes, wrong output
    snap.write_text(json.dumps(corrupted) + "\n", encoding="utf-8")

    results = list(check_belief_nonreproducible(ctx))
    assert any(r.severity is Severity.ERROR for r in results)


def test_nonreproducible_silent_when_inputs_changed(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    # Different input_hashes -> legitimate change, not flagged, even if belief differs.
    stale = rows[0] | {"belief_state": "speculative", "input_hashes": ["sha256:stale"]}
    snap.write_text(json.dumps(stale) + "\n", encoding="utf-8")
    assert list(check_belief_nonreproducible(ctx)) == []


def test_nonreproducible_errors_on_corrupted_scalar_band(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    # Enable the scalar so bands are recorded and compared (#3: scalar fields are golden too).
    (tmp_path / "core").mkdir(parents=True, exist_ok=True)
    (tmp_path / "core" / "decisions.md").write_text(
        "# Decisions\n\n## D-1: on\n- **Status:** active\n- **Feature flag:** belief-scalar\n",
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    # Same belief_state/contested/inputs, corrupted band -> must still ERROR when scalar enabled.
    corrupted = rows[0] | {"net_band": [0.0, 0.0]}
    snap.write_text(json.dumps(corrupted) + "\n", encoding="utf-8")
    results = list(check_belief_nonreproducible(ctx))
    assert any(r.severity is Severity.ERROR for r in results)


def test_nonreproducible_errors_on_corrupted_diagnostic_count(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_support_plus_diagnostic_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    corrupted = rows[0] | {"diagnostic_dispute_count": 0}
    snap.write_text(json.dumps(corrupted) + "\n", encoding="utf-8")
    results = list(check_belief_nonreproducible(ctx))
    assert any(r.severity is Severity.ERROR for r in results)


def test_nonreproducible_uses_latest_matching_row_not_latest_per_claim(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    matching_corrupted = rows[0] | {"belief_state": "speculative"}
    stale_later = rows[0] | {"input_hashes": ["sha256:stale"], "belief_state": "speculative"}
    # Old latest-per-claim logic would inspect only the stale later row and skip. Correct
    # latest-matching logic still finds the earlier row with current inputs and errors.
    snap.write_text(
        json.dumps(matching_corrupted) + "\n" + json.dumps(stale_later) + "\n",
        encoding="utf-8",
    )
    results = list(check_belief_nonreproducible(ctx))
    assert any(r.severity is Severity.ERROR for r in results)


def test_nonreproducible_silent_when_policy_identity_differs(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    # Same inputs, WRONG belief, but a different policy_version -> not comparable, no error.
    other_policy = rows[0] | {"belief_state": "speculative", "policy_version": "2"}
    snap.write_text(json.dumps(other_policy) + "\n", encoding="utf-8")
    assert list(check_belief_nonreproducible(ctx)) == []


def test_nonreproducible_normalizes_pre_policy_stored_row(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    # A legacy stored row (no policy fields) with corrupted belief. read_snapshots normalizes
    # it to core-default/1 == the recomputed identity, so corruption is still caught.
    legacy = {k: v for k, v in rows[0].items() if k not in ("policy_id", "policy_version")}
    legacy["belief_state"] = "speculative"
    snap.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
    results = list(check_belief_nonreproducible(ctx))
    assert any(r.severity is Severity.ERROR for r in results)


def test_nonreproducible_silent_when_authored_capped_absent(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    # Simulate a pre-Slice-B history line: strip authored_capped from the (otherwise correct)
    # row. read_snapshots normalizes it back to False, matching the current empirical result.
    legacy = {k: v for k, v in rows[0].items() if k != "authored_capped"}
    snap.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
    assert list(check_belief_nonreproducible(ctx)) == []


def test_nonreproducible_errors_when_authored_capped_mismatches(tmp_path: Path):
    import json

    from science_tool.graph.belief_snapshot import make_snapshots
    from science_tool.validate.checks.evidence_lines import check_belief_nonreproducible

    _write_two_support_graph(tmp_path)
    ctx = _ctx(tmp_path)
    rows = make_snapshots(tmp_path / "knowledge" / "graph.trig", as_of="2026-05-24")
    snap = tmp_path / "knowledge" / "belief-snapshots.jsonl"
    # Same inputs, but stored authored_capped=True while the empirical recompute is False.
    # authored_capped is a golden output, so the divergence must be flagged.
    corrupted = rows[0] | {"authored_capped": True}
    snap.write_text(json.dumps(corrupted) + "\n", encoding="utf-8")
    results = list(check_belief_nonreproducible(ctx))
    assert any(r.severity is Severity.ERROR for r in results)
