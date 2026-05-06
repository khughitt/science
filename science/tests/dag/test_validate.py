"""Unit tests for science_tool.dag.validate."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from science_tool.dag.paths import load_dag_paths
from science_tool.dag.validate import (
    ValidationFinding,
    ValidationReport,
    validate_project,
)


FIXTURE_MINIMAL = Path(__file__).parent / "fixtures" / "minimal"


@pytest.fixture
def _schema_cache_isolation() -> Iterator[None]:
    """Clear the _load_schema cache after the test so monkeypatched _SCHEMA_PATH
    doesn't leak stale schema bytes into subsequent tests."""
    yield
    import science_tool.dag.validate as v

    v._load_schema.cache_clear()


def test_validation_report_ok_on_clean_fixture() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "clean")
    report = validate_project(paths)
    assert isinstance(report, ValidationReport)
    assert report.ok, f"unexpected findings: {report.findings}"
    assert report.strict is False
    assert report.findings == ()


def test_validation_report_to_json_shape() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "clean")
    report = validate_project(paths)
    js = report.to_json()
    assert js["ok"] is True
    assert js["strict"] is False
    assert js["findings"] == []
    assert "today" in js


def test_validation_finding_severity_literal() -> None:
    # strict_error findings must not block when strict=False
    finding = ValidationFinding(
        dag="x",
        edge_id=1,
        rule="identification_missing",
        severity="strict_error",
        message="missing",
        location="x.edges.yaml",
    )
    report = ValidationReport(today=date.today(), strict=False, findings=(finding,))
    assert report.ok is True  # strict_error does not block when strict=False

    strict_report = ValidationReport(today=date.today(), strict=True, findings=(finding,))
    assert strict_report.ok is False  # strict_error blocks when strict=True


def test_posterior_beta_must_be_finite() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "bad-posterior-infinite")
    report = validate_project(paths)
    assert not report.ok
    rules = {f.rule for f in report.findings}
    assert "posterior_finite" in rules
    finite_finding = next(f for f in report.findings if f.rule == "posterior_finite")
    assert finite_finding.severity == "error"
    assert finite_finding.edge_id == 1


def test_posterior_hdi_must_be_ordered() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "bad-posterior-hdi-order")
    report = validate_project(paths)
    assert not report.ok
    rules = {f.rule for f in report.findings}
    assert "posterior_hdi_ordered" in rules


def test_posterior_prob_sign_must_be_in_unit_interval() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "bad-posterior-prob-sign")
    report = validate_project(paths)
    assert not report.ok
    rules = {f.rule for f in report.findings}
    assert "posterior_prob_sign_range" in rules


def test_yaml_missing_edge_present_in_dot() -> None:
    # .dot has a->c; YAML does not.
    paths = load_dag_paths(FIXTURE_MINIMAL / "yaml-dot-mismatch")
    report = validate_project(paths)
    rules = {f.rule for f in report.findings}
    assert "topology_missing_in_yaml" in rules


def test_yaml_edge_not_in_dot() -> None:
    # YAML has edge id=2 with target=zzz; .dot has no such node.
    paths = load_dag_paths(FIXTURE_MINIMAL / "yaml-dot-mismatch")
    report = validate_project(paths)
    rules = {f.rule for f in report.findings}
    # zzz is missing from .dot; check surfaces as topology_node_mismatch
    # (the node doesn't exist) rather than topology_missing_in_dot.
    assert "topology_node_mismatch" in rules


def test_clean_fixture_has_no_topology_findings() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "clean")
    report = validate_project(paths)
    topology_rules = {
        "topology_missing_in_yaml",
        "topology_missing_in_dot",
        "topology_node_mismatch",
    }
    assert not topology_rules.intersection(f.rule for f in report.findings)


def test_acyclicity_flags_cycle() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "cyclic")
    report = validate_project(paths)
    acyclicity_findings = [f for f in report.findings if f.rule == "acyclicity"]
    assert len(acyclicity_findings) == 1
    msg = acyclicity_findings[0].message
    # The cycle path must mention all three nodes.
    assert "a" in msg and "b" in msg and "c" in msg


def test_acyclicity_passes_on_clean() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "clean")
    report = validate_project(paths)
    assert not any(f.rule == "acyclicity" for f in report.findings)


def test_jsonschema_conformance_passes_on_clean() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "clean")
    report = validate_project(paths)
    assert not any(f.rule == "jsonschema_conformance" for f in report.findings)


def test_jsonschema_conformance_runs_on_mm30_fixture() -> None:
    # Primary value is proving the check runs on a real multi-edge fixture
    # without falsely flagging. If the committed schema drifts, this also
    # catches that (though test_committed_schema_matches_pydantic_emit is the
    # dedicated drift-guard).
    paths = load_dag_paths(Path(__file__).parent / "fixtures" / "mm30")
    report = validate_project(paths)
    jsonschema_findings = [f for f in report.findings if f.rule == "jsonschema_conformance"]
    assert jsonschema_findings == []


def test_jsonschema_conformance_catches_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _schema_cache_isolation
) -> None:
    # Point the schema loader at a bogus schema that rejects everything, then
    # ensure at least one finding with rule=jsonschema_conformance appears.
    bogus = tmp_path / "bogus.schema.json"
    bogus.write_text(
        '{"type": "object", "properties": {"dag": {"type": "number"}}, "required": ["dag"]}',
        encoding="utf-8",
    )
    import science_tool.dag.validate as v

    monkeypatch.setattr(v, "_SCHEMA_PATH", bogus)
    # Re-clear the cache so the bogus schema is picked up.
    v._load_schema.cache_clear()

    paths = load_dag_paths(FIXTURE_MINIMAL / "clean")
    report = validate_project(paths)
    rules = {f.rule for f in report.findings}
    assert "jsonschema_conformance" in rules


def test_strict_flags_missing_identification() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "missing-identification")
    # Non-strict: deprecation warning only, no strict_error exit.
    non_strict = validate_project(paths, strict=False)
    assert non_strict.ok, non_strict.findings

    strict = validate_project(paths, strict=True)
    assert not strict.ok
    rules_strict = {f.rule for f in strict.findings if f.severity == "strict_error"}
    assert "identification_missing" in rules_strict


def test_strict_flags_empty_description() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "empty-description")
    strict = validate_project(paths, strict=True)
    rules = {f.rule for f in strict.findings if f.severity == "strict_error"}
    assert "description_nonempty" in rules


def test_strict_flags_orphan_dot_node() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "orphan-dot-node")
    strict = validate_project(paths, strict=True)
    rules = {f.rule for f in strict.findings if f.severity == "strict_error"}
    assert "dot_nodes_unused" in rules
    msg = next(f.message for f in strict.findings if f.rule == "dot_nodes_unused")
    assert "orphan" in msg


def test_strict_flags_cross_dag_node_case_mismatch() -> None:
    paths = load_dag_paths(FIXTURE_MINIMAL / "cross-dag-inconsistent")
    strict = validate_project(paths, strict=True)
    rules = {f.rule for f in strict.findings if f.severity == "strict_error"}
    assert "cross_dag_node_consistency" in rules
    # And the non-strict variant should NOT block on this.
    non_strict = validate_project(paths, strict=False)
    assert non_strict.ok


def test_non_strict_does_not_emit_strict_errors_as_blocking() -> None:
    # missing-identification fixture: strict_error exists but doesn't block
    # non-strict run.
    paths = load_dag_paths(FIXTURE_MINIMAL / "missing-identification")
    non_strict = validate_project(paths, strict=False)
    assert non_strict.ok
    # The strict_error finding may still be emitted for JSON surface.
    all_rules = {f.rule for f in non_strict.findings}
    # Emitting strict_errors in non-strict output is allowed but not required;
    # we only assert that non-strict exits OK.
    _ = all_rules  # suppress "unused variable" warning


def test_mm30_fixture_validates_non_strict() -> None:
    paths = load_dag_paths(Path(__file__).parent / "fixtures" / "mm30")
    report = validate_project(paths)
    assert report.ok, "\n".join(str(f) for f in report.findings)


def test_mm30_fixture_validates_strict() -> None:
    # Per Phase 1, every mm30 fixture edge has explicit identification:.
    paths = load_dag_paths(Path(__file__).parent / "fixtures" / "mm30")
    report = validate_project(paths, strict=True)
    blocking = [f for f in report.findings if report._blocks(f)]
    assert not blocking, "\n".join(str(f) for f in blocking)
