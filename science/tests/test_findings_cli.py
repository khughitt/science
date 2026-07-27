import json

from click.testing import CliRunner

from science_tool.findings.cli import findings_group


def _report_json() -> dict:
    return {
        "schema_version": 2,
        "fingerprint_version": 1,
        "ingestion_ref": "ing:1",
        "generated_at": "2026-07-27T12:00:00+00:00",
        "findings": [],
        "accepted": [],
        "metrics": {},
        "unwired": [],
        "totals": {
            "findings_total": 0,
            "findings_by_severity": {},
            "accepted_total": 0,
            "unwired_total": 0,
        },
        "meta": {"producers_run": [], "total_duration_seconds": 0.0, "timings": []},
    }


def test_ingest_reports_what_it_did(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")
    result = CliRunner().invoke(
        findings_group,
        ["ingest", str(report), "--project-root", str(tmp_path), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["records_written"] == 0


def test_ingest_exits_nonzero_on_a_refused_report(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    result = CliRunner().invoke(
        findings_group, ["ingest", str(report), "--project-root", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert "schema_version" in result.output


def test_list_on_a_project_with_no_cases_is_empty_and_exits_zero(tmp_path):
    result = CliRunner().invoke(
        findings_group, ["list", "--project-root", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []


def test_an_unknown_status_is_rejected_rather_than_matching_nothing(tmp_path):
    result = CliRunner().invoke(
        findings_group,
        ["list", "--project-root", str(tmp_path), "--status", "confirmd"],
    )
    assert result.exit_code == 2
    assert "confirmd" in result.output


def test_the_offered_statuses_are_the_models_statuses(tmp_path):
    from science_model.audit import CASE_STATUSES

    result = CliRunner().invoke(findings_group, ["list", "--help"])
    assert result.exit_code == 0
    for status in CASE_STATUSES:
        assert status in result.output
    assert set(CASE_STATUSES) == {"proposed", "confirmed", "dismissed", "promoted"}
