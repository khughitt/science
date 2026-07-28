import json

import pytest
from click.testing import CliRunner

import science_tool.findings.cli as findings_cli
from science_tool.findings.cli import findings_group
from science_tool.findings.producers import FindingProducer, build_registry


REGISTRY = build_registry(
    [
        FindingProducer(
            producer_id="dataset_anomalies",
            namespace="health_checks",
            source_module="graph/health_checks/test.py",
            rules=(),
            sections=(),
            metrics_schema=None,
            remediators=frozenset(),
        )
    ],
    active_kinds=frozenset(),
)


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
        "meta": {
            "producers_run": ["dataset_anomalies"],
            "total_duration_seconds": 0.0,
            "timings": [],
        },
    }


def _attestation_args() -> list[str]:
    return [
        "--attest-ingestion-ref",
        "ing:1",
        "--attest-generated-at",
        "2026-07-27T12:00:00+00:00",
        "--attest-producer-id",
        "dataset_anomalies",
    ]


def test_ingest_reports_what_it_did(tmp_path, monkeypatch):
    monkeypatch.setattr(findings_cli, "_registry", lambda _entity_registry: REGISTRY)
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")
    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            "--format",
            "json",
            *_attestation_args(),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["records_written"] == 0


def test_ingest_exits_nonzero_on_a_refused_report(tmp_path):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            *_attestation_args(),
        ],
    )
    assert result.exit_code == 2
    assert "schema_version" in result.output


@pytest.mark.parametrize(
    "missing_option",
    [
        "--attest-ingestion-ref",
        "--attest-generated-at",
        "--attest-producer-id",
    ],
)
def test_ingest_requires_each_explicit_attestation_flag(tmp_path, missing_option):
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")
    attestation = _attestation_args()
    index = attestation.index(missing_option)
    del attestation[index : index + 2]

    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            *attestation,
        ],
    )

    assert result.exit_code == 2
    assert f"Missing option '{missing_option}'" in result.output


def test_ingest_refuses_a_report_attestation_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(findings_cli, "_registry", lambda _entity_registry: REGISTRY)
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")
    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            "--attest-ingestion-ref",
            "different",
            "--attest-generated-at",
            "2026-07-27T12:00:00+00:00",
            "--attest-producer-id",
            "dataset_anomalies",
        ],
    )

    assert result.exit_code == 2
    assert "ingestion_ref" in result.output
    assert not (tmp_path / "doc" / "audits" / "cases").exists()


def test_ingest_cli_refuses_graph_identity_collisions_before_case_writes(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(findings_cli, "_registry", lambda _entity_registry: REGISTRY)
    for name in ("q1.md", "q1-duplicate.md"):
        path = tmp_path / "entities" / "questions" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\nid: question:q1\nkind: question\ntitle: Q1\n---\n",
            encoding="utf-8",
        )
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")

    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            *_attestation_args(),
        ],
    )

    assert result.exit_code == 2
    assert "question:q1" in result.output
    assert not (tmp_path / "doc" / "audits" / "cases").exists()


def test_ingest_cli_wraps_malformed_graph_configuration_as_a_refusal(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(findings_cli, "_registry", lambda _entity_registry: REGISTRY)
    (tmp_path / "science.yaml").write_text(
        "name: [unterminated\n",
        encoding="utf-8",
    )
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")

    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            *_attestation_args(),
        ],
    )

    assert result.exit_code == 2
    assert "refused:" in result.output
    assert not (tmp_path / "doc" / "audits" / "cases").exists()


@pytest.mark.parametrize("configuration", ["- not-a-mapping\n", "42\n"])
def test_ingest_cli_refuses_non_mapping_graph_configuration(
    tmp_path,
    monkeypatch,
    configuration,
):
    monkeypatch.setattr(findings_cli, "_registry", lambda: REGISTRY)
    (tmp_path / "science.yaml").write_text(configuration, encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")

    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            *_attestation_args(),
        ],
    )

    assert result.exit_code == 2
    assert "mapping" in result.output
    assert not (tmp_path / "doc" / "audits" / "cases").exists()


def test_ingest_cli_wraps_commons_context_failures_as_zero_write_refusals(
    tmp_path,
    monkeypatch,
):
    from science_tool.commons.errors import CommonsError

    monkeypatch.setattr(findings_cli, "_registry", lambda: REGISTRY)

    def fail_context(_project_root):
        raise CommonsError("commons identity context unavailable")

    monkeypatch.setattr(findings_cli, "_load_ingestion_context", fail_context)
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_report_json()), encoding="utf-8")

    result = CliRunner().invoke(
        findings_group,
        [
            "ingest",
            str(report),
            "--project-root",
            str(tmp_path),
            *_attestation_args(),
        ],
    )

    assert result.exit_code == 2
    assert "commons identity context unavailable" in result.output
    assert not (tmp_path / "doc" / "audits" / "cases").exists()


def test_list_on_a_project_with_no_cases_is_empty_and_exits_zero(tmp_path):
    result = CliRunner().invoke(findings_group, ["list", "--project-root", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []


@pytest.mark.parametrize("name", ["notes.md", ".hidden.md"])
def test_list_refuses_every_markdown_leaf_that_is_not_a_bound_case(tmp_path, name):
    cases = tmp_path / "doc" / "audits" / "cases"
    cases.mkdir(parents=True)
    (cases / name).write_text("not a case", encoding="utf-8")

    result = CliRunner().invoke(findings_group, ["list", "--project-root", str(tmp_path)])

    assert result.exit_code == 2
    assert name in result.output


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
