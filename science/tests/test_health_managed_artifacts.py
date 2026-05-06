"""Health report integration: managed-artifact rows + total_issues contribution."""

from pathlib import Path

from science_tool.graph.health import build_health_report


def test_health_report_includes_managed_artifacts_section(tmp_path: Path) -> None:
    """A project where validate.sh is missing should surface a managed-artifact finding."""
    (tmp_path / "science.yaml").write_text("name: x\n", encoding="utf-8")
    report = build_health_report(tmp_path)
    assert "managed_artifacts" in report
    findings = report["managed_artifacts"]
    names = {f["name"] for f in findings}
    assert "validate.sh" in names
    missing = next(f for f in findings if f["name"] == "validate.sh")
    assert missing["status"] == "missing"


def test_total_issues_includes_missing_artifact(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: x\n", encoding="utf-8")
    report = build_health_report(tmp_path)
    # total_issues exists in the existing report; assert it now counts our finding.
    assert report.get("total_issues", 0) >= 1


def test_current_artifact_does_not_count(tmp_path: Path) -> None:
    """If validate.sh is current, no contribution to total_issues."""
    from science_tool.project_artifacts import canonical_path

    (tmp_path / "science.yaml").write_text("name: x\n", encoding="utf-8")
    target = tmp_path / "validate.sh"
    target.write_bytes(canonical_path("validate.sh").read_bytes())
    target.chmod(0o755)
    report = build_health_report(tmp_path)
    findings = [f for f in report["managed_artifacts"] if f["status"] != "current"]
    assert findings == [] or all(f["status"] == "pinned" for f in findings)
