import json
from pathlib import Path

from click.testing import CliRunner
from science_model.audit import AuditReport

from science_tool.budget.measure import visible_len
from science_tool.budget.registry import BUDGETS
from science_tool.cli import main


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
