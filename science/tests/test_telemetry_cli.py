"""Tests for telemetry CLI instrumentation and reporting commands."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.telemetry import append_event, read_events
from science_tool.validate import Check, Result, Severity, ValidateContext
from science_tool.validate.checks import clear_checks_for_tests


def test_successful_cli_invocation_records_command_finish(tmp_path: Path) -> None:
    telemetry_dir = tmp_path / "telemetry"
    feedback_dir = tmp_path / "feedback"
    env = {"SCIENCE_TELEMETRY_DIR": str(telemetry_dir), "SCIENCE_FEEDBACK_DIR": str(feedback_dir)}

    result = CliRunner().invoke(main, ["feedback", "list", "--format", "json"], env=env)

    assert result.exit_code == 0, result.output
    events = read_events(telemetry_dir)
    assert len(events) == 1
    assert events[0]["event_type"] == "command_finish"
    assert events[0]["command"] == "feedback list"
    assert events[0]["exit_code"] == 0
    assert events[0]["argv_shape"] == ["feedback", "list", "--format", "<value>"]


def test_click_parse_error_records_command_error(tmp_path: Path) -> None:
    telemetry_dir = tmp_path / "telemetry"
    env = {"SCIENCE_TELEMETRY_DIR": str(telemetry_dir), "SCIENCE_FEEDBACK_DIR": str(tmp_path / "feedback")}

    result = CliRunner().invoke(main, ["feedback", "list", "--bad-option"], env=env)

    assert result.exit_code != 0
    events = read_events(telemetry_dir)
    assert len(events) == 1
    assert events[0]["event_type"] == "command_error"
    assert events[0]["command"] == "feedback list"
    assert events[0]["error_class"] == "NoSuchOption"
    assert events[0]["exit_code"] == 2


def test_telemetry_group_preserves_nonzero_ctx_exit(tmp_path: Path) -> None:
    clear_checks_for_tests()

    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.ERROR, Path("science.yaml"), 1, "broken", "demo.error", None)]

    project = tmp_path / "project"
    project.mkdir()
    project.joinpath("science.yaml").write_text("name: demo\n", encoding="utf-8")
    telemetry_dir = tmp_path / "telemetry"
    try:
        result = CliRunner().invoke(
            main,
            ["validate", "--project-root", str(project)],
            env={"SCIENCE_TELEMETRY_DIR": str(telemetry_dir)},
        )
    finally:
        clear_checks_for_tests()

    assert result.exit_code == 1
    assert "FAILED: 1 error(s)" in result.output


def test_telemetry_can_be_disabled_with_environment_flag(tmp_path: Path) -> None:
    telemetry_dir = tmp_path / "telemetry"
    env = {
        "SCIENCE_TELEMETRY_DIR": str(telemetry_dir),
        "SCIENCE_FEEDBACK_DIR": str(tmp_path / "feedback"),
        "SCIENCE_TELEMETRY_ENABLED": "0",
    }

    result = CliRunner().invoke(main, ["feedback", "list", "--format", "json"], env=env)

    assert result.exit_code == 0, result.output
    assert read_events(telemetry_dir) == []


def test_telemetry_status_json_reports_directory_and_event_count(tmp_path: Path) -> None:
    telemetry_dir = tmp_path / "telemetry"
    append_event(telemetry_dir, {"event_id": "one", "timestamp": "2026-06-27T10:00:00-04:00"})
    env = {"SCIENCE_TELEMETRY_DIR": str(telemetry_dir)}

    result = CliRunner().invoke(main, ["telemetry", "status", "--format", "json"], env=env)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["rows"][0]["telemetry_dir"] == str(telemetry_dir)
    assert payload["rows"][0]["enabled"] is True
    assert payload["rows"][0]["event_count"] == 1


def test_telemetry_report_json_summarizes_local_events(tmp_path: Path) -> None:
    telemetry_dir = tmp_path / "telemetry"
    append_event(
        telemetry_dir,
        {
            "event_id": "finish",
            "event_type": "command_finish",
            "command": "feedback list",
            "exit_code": 0,
            "timestamp": "2026-06-27T10:00:00-04:00",
        },
    )
    append_event(
        telemetry_dir,
        {
            "event_id": "error",
            "event_type": "command_error",
            "command": "feedback list",
            "error_class": "NoSuchOption",
            "exit_code": 2,
            "timestamp": "2026-06-27T10:01:00-04:00",
        },
    )

    result = CliRunner().invoke(main, ["telemetry", "report", "--format", "json"], env={"SCIENCE_TELEMETRY_DIR": str(telemetry_dir)})

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["rows"][0]["total_events"] == 2
    assert payload["rows"][0]["commands"]["feedback list"] == 2
    assert payload["rows"][0]["error_classes"]["NoSuchOption"] == 1


def test_telemetry_export_jsonl_prints_events(tmp_path: Path) -> None:
    telemetry_dir = tmp_path / "telemetry"
    append_event(
        telemetry_dir,
        {
            "event_id": "finish",
            "event_type": "command_finish",
            "command": "feedback list",
            "timestamp": "2026-06-27T10:00:00-04:00",
        },
    )

    result = CliRunner().invoke(main, ["telemetry", "export", "--format", "jsonl"], env={"SCIENCE_TELEMETRY_DIR": str(telemetry_dir)})

    assert result.exit_code == 0, result.output
    assert json.loads(result.output.splitlines()[0])["event_id"] == "finish"


def test_telemetry_prune_removes_old_events(tmp_path: Path) -> None:
    telemetry_dir = tmp_path / "telemetry"
    append_event(telemetry_dir, {"event_id": "old", "timestamp": "2026-05-31T23:59:00-04:00"})
    append_event(telemetry_dir, {"event_id": "new", "timestamp": "2026-06-01T00:00:00-04:00"})

    result = CliRunner().invoke(
        main,
        ["telemetry", "prune", "--before", "2026-06-01", "--format", "json"],
        env={"SCIENCE_TELEMETRY_DIR": str(telemetry_dir)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["rows"][0]["removed"] == 1
    event_ids = {event.get("event_id") for event in read_events(telemetry_dir)}
    assert "old" not in event_ids
    assert "new" in event_ids
