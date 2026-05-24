from pathlib import Path

from rdflib import Dataset, Literal, RDF, URIRef

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
