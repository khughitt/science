import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from science_model.audit import AuditReport, PathSubject, ProducerMetrics

from science_tool.budget.measure import visible_len
from science_tool.budget.registry import BUDGETS
from science_tool.cli import main
from science_tool.findings.catalog import build_project_registry
from science_tool.findings.producers import FindingProducerResult
from science_tool.findings.reporting import build_audit_report
from science_tool.graph.health import HealthExecution
from science_tool.instruments import InstrumentResult
from science_tool.validate.checks.manifest import RULES as MANIFEST_RULES


def test_health_json_stdout_is_a_complete_valid_audit_report(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks" / "active"
    tasks.mkdir(parents=True)
    for index in range(45):
        (tasks / f"t{index:03d}.md").write_text(
            f"---\nid: t{index:03d}\ntitle: task {index}\ntype: dev\npriority: P1\n"
            "status: proposed\naspects: []\ncreated: 2026-04-13\n---\nbody\n",
            encoding="utf-8",
        )

    result = CliRunner().invoke(
        main,
        [
            "health",
            "--project-root",
            str(tmp_path),
            "--format",
            "json",
            "--check",
            "legacy_task_type",
        ],
    )
    assert result.exit_code == 0, result.output
    report = AuditReport.model_validate_json(result.output)
    assert len(report.findings) == 45
    assert report.totals.findings_total == 45


def test_health_output_file_receives_complete_report(tmp_path: Path) -> None:
    output = tmp_path / "health.json"
    result = CliRunner().invoke(
        main,
        [
            "health",
            "--project-root",
            str(tmp_path),
            "--format",
            "json",
            "--check",
            "tooling_scaffold",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["totals"]["findings_total"] == 1


def test_health_table_reports_findings_hidden_by_severity(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks" / "active"
    tasks.mkdir(parents=True)
    (tasks / "t001.md").write_text(
        "---\nid: t001\ntitle: task\ntype: dev\npriority: P1\n"
        "status: proposed\naspects: []\ncreated: 2026-04-13\n---\nbody\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main,
        [
            "health",
            "--project-root",
            str(tmp_path),
            "--check",
            "legacy_task_type",
            "--severity",
            "error",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Findings displayed: 0 of 1 total." in result.output
    assert "Project is clean." not in result.output


def test_health_table_reports_section_cap_and_stays_within_budget(
    tmp_path: Path,
) -> None:
    tasks = tmp_path / "tasks" / "active"
    tasks.mkdir(parents=True)
    for index in range(45):
        (tasks / f"t{index:03d}.md").write_text(
            f"---\nid: t{index:03d}\ntitle: task {index}\ntype: dev\npriority: P1\n"
            "status: proposed\naspects: []\ncreated: 2026-04-13\n---\nbody\n",
            encoding="utf-8",
        )

    result = CliRunner().invoke(
        main,
        [
            "health",
            "--project-root",
            str(tmp_path),
            "--check",
            "legacy_task_type",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Findings displayed: 40 of 45 total." in result.output
    assert visible_len(result.output) <= BUDGETS["health"].max_chars


def _write_manifest_with_acceptance(root: Path, entry: object) -> None:
    (root / "science.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "test",
                "created": "2026-07-29",
                "last_modified": "2026-07-29",
                "status": "active",
                "profile": "research",
                "layout_version": 3,
                "knowledge_profiles": {"local": "local"},
                "health": {"accepted_validation": [entry]},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("entry", "expected_rule"),
    [
        (
            {"rule": "manifest.check", "severity": "warning", "reason": "reviewed"},
            "accepted-validation.legacy-shape",
        ),
        (
            {"finding_id": "not-a-fingerprint", "reason": "reviewed"},
            "accepted-validation.invalid-entry",
        ),
    ],
)
@pytest.mark.parametrize("mode", ["table", "json-stdout", "json-output"])
def test_unapplied_acceptance_configuration_exits_2_after_complete_output(
    tmp_path: Path,
    entry: object,
    expected_rule: str,
    mode: str,
) -> None:
    _write_manifest_with_acceptance(tmp_path, entry)
    args = [
        "health",
        "--project-root",
        str(tmp_path),
        "--check",
        "validate",
    ]
    output = tmp_path / "health.json"
    if mode == "json-stdout":
        args += ["--format", "json"]
    elif mode == "json-output":
        args += ["--format", "json", "--output", str(output)]

    result = CliRunner().invoke(main, args)

    assert result.exit_code == 2, result.output
    if mode == "table":
        normalized_output = " ".join(result.output.split())
        assert "accepted validation (1)" in normalized_output
        assert "manifest.check" in normalized_output
    else:
        report = AuditReport.model_validate_json(
            output.read_text(encoding="utf-8") if mode == "json-output" else result.output
        )
        rule_ids = {item.finding.rule_id for item in report.findings}
        assert expected_rule in rule_ids
        assert "manifest.check" in rule_ids
        if mode == "json-output":
            assert "wrote the complete health report" in result.output


def test_ordinary_error_finding_does_not_gate_health(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import science_tool.graph.health as health

    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    registry = build_project_registry(tmp_path)
    finding = MANIFEST_RULES["manifest.check"].build(
        subject=PathSubject(path="science.yaml"),
        severity="error",
        qualifiers={"key": ["summary"]},
        message="missing summary",
    )
    report = build_audit_report(
        producer_results={
            "validate": FindingProducerResult(
                instrument=InstrumentResult.from_rows([finding]),
                metrics=ProducerMetrics.model_validate(
                    {
                        "verified": 0,
                        "unverifiable": 0,
                        "mismatch": 0,
                        "error": 0,
                    }
                ),
            )
        },
        registry=registry,
        ingestion_ref="health:test",
        generated_at="2026-07-29T12:00:00+00:00",
        total_duration_seconds=0,
    )
    monkeypatch.setattr(
        health,
        "execute_health_report",
        lambda *_args, **_kwargs: HealthExecution(report=report, registry=registry),
    )

    result = CliRunner().invoke(
        main,
        [
            "health",
            "--project-root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    emitted = AuditReport.model_validate_json(result.output)
    assert emitted.totals.findings_by_severity["error"] == 1
