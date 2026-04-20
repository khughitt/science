"""Unit tests for science_tool.dag.validate."""

from __future__ import annotations

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
