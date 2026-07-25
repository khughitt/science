# science/tests/test_belief_basis_cli.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF

from science_tool.graph.belief import EVIDENCE_LINE_CLASS
from science_tool.graph.cli import graph_group
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.store.identity import graph_uri

CLAIM = URIRef(PROJECT_NS["proposition/p"])
LINE = URIRef(PROJECT_NS["evidence-line/e"])


def _write_graph(path: Path, *, with_line: bool) -> None:
    dataset = Dataset()
    knowledge = dataset.graph(graph_uri("graph/knowledge"))
    provenance = dataset.graph(graph_uri("graph/provenance"))
    knowledge.add((CLAIM, RDF.type, SCI_NS.Proposition))
    if with_line:
        knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
        knowledge.add((LINE, CITO_NS.supports, CLAIM))
        provenance.add((LINE, SCI_NS.evidenceStrength, Literal("strong")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dataset.serialize(format="trig"))


def _snapshot(graph_path: Path, out: Path) -> None:
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--out", str(out)]
    )
    assert result.exit_code == 0, result.output


def test_snapshot_writes_verified_rows(tmp_path: Path):
    graph_path, out = tmp_path / "graph.trig", tmp_path / "basis.json"
    _write_graph(graph_path, with_line=True)
    _snapshot(graph_path, out)
    payload = json.loads(out.read_text())
    assert payload["digest"] and payload["schema_version"] == 1
    assert any(row["entity_id"] == "proposition:p" for row in payload["rows"])


def test_out_and_compare_are_mutually_exclusive(tmp_path: Path):
    """Passing the same path for both would overwrite the baseline and report clean."""
    graph_path, out = tmp_path / "graph.trig", tmp_path / "basis.json"
    _write_graph(graph_path, with_line=True)
    _snapshot(graph_path, out)
    result = CliRunner().invoke(
        graph_group,
        ["belief-basis", "--graph-path", str(graph_path), "--out", str(out), "--compare", str(out)],
    )
    assert result.exit_code == 2
    assert "mutually exclusive" in result.output


def test_compare_detects_an_added_evidence_line(tmp_path: Path):
    graph_path, baseline = tmp_path / "graph.trig", tmp_path / "before.json"
    _write_graph(graph_path, with_line=False)
    _snapshot(graph_path, baseline)

    _write_graph(graph_path, with_line=True)
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--compare", str(baseline)]
    )
    assert result.exit_code == 1
    assert "proposition:p" in result.output and "units" in result.output


def test_identical_graph_compares_clean(tmp_path: Path):
    graph_path, baseline = tmp_path / "graph.trig", tmp_path / "before.json"
    _write_graph(graph_path, with_line=True)
    _snapshot(graph_path, baseline)
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--compare", str(baseline)]
    )
    assert result.exit_code == 0


def test_unwired_graph_exits_two_not_zero(tmp_path: Path):
    """A graph with no typed entities must NOT report clean."""
    graph_path = tmp_path / "graph.trig"
    graph_path.write_text(Dataset().serialize(format="trig"))
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--out", str(tmp_path / "o.json")]
    )
    assert result.exit_code == 2
    assert "no_typed_entities" in result.output


def test_missing_graph_is_unwired_not_moved(tmp_path: Path):
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(tmp_path / "absent.trig"), "--out", str(tmp_path / "o.json")]
    )
    assert result.exit_code == 2


def test_tampered_baseline_is_unwired_not_clean(tmp_path: Path):
    """A corrupted baseline must never yield a clean comparison."""
    graph_path, baseline = tmp_path / "graph.trig", tmp_path / "before.json"
    _write_graph(graph_path, with_line=True)
    _snapshot(graph_path, baseline)
    payload = json.loads(baseline.read_text())
    # Target by entity_id, not position: rows are sorted by URI, and
    # "evidence-line:e" sorts before "proposition:p" and already has empty
    # unit_keys, so a positional rows[0] edit is a no-op that leaves the
    # digest unchanged and the baseline still (correctly) trusted.
    row = next(r for r in payload["rows"] if r["entity_id"] == "proposition:p")
    row["unit_keys"] = []
    baseline.write_text(json.dumps(payload))
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--compare", str(baseline)]
    )
    assert result.exit_code == 2
    assert "digest mismatch" in result.output


def test_malformed_baseline_json_is_unwired(tmp_path: Path):
    graph_path, baseline = tmp_path / "graph.trig", tmp_path / "before.json"
    _write_graph(graph_path, with_line=True)
    baseline.write_text("{not json")
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--compare", str(baseline)]
    )
    assert result.exit_code == 2


def test_json_array_baseline_is_unwired_not_moved(tmp_path: Path):
    """Valid JSON of the wrong shape must not escape as exit 1.

    `BasisSnapshot(**payload)` on a list raises TypeError, which the handler would
    miss; load_snapshot uses model_validate so this is a caught ValidationError.
    """
    graph_path, baseline = tmp_path / "graph.trig", tmp_path / "before.json"
    _write_graph(graph_path, with_line=True)
    baseline.write_text("[]")
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--compare", str(baseline)]
    )
    assert result.exit_code == 2


def test_capture_serialization_failure_is_unwired(tmp_path: Path, monkeypatch):
    """A basis that cannot be serialized is uncomputable, not a belief movement.

    unit_key raises TypeError by design on a non-JSON-native field value; that
    must reach exit 2 rather than escaping as exit 1.
    """
    def _boom(*_args, **_kwargs):
        raise TypeError("Object of type object is not JSON serializable")

    monkeypatch.setattr("science_tool.graph.belief_basis.capture_basis", _boom)
    graph_path = tmp_path / "graph.trig"
    _write_graph(graph_path, with_line=True)
    result = CliRunner().invoke(
        graph_group, ["belief-basis", "--graph-path", str(graph_path), "--out", str(tmp_path / "o.json")]
    )
    assert result.exit_code == 2
    assert "could not compute basis" in result.output
