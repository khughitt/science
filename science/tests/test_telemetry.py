"""Tests for local-first telemetry storage and reporting."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from science_tool.telemetry import (
    append_event,
    export_events_jsonl,
    feedback_context_from_recent_event,
    format_feedback_telemetry,
    get_telemetry_dir,
    new_event,
    new_validation_summary_event,
    prune_events,
    read_events,
    redact_argv,
    summarize_recent_for_feedback_target,
    summarize_events,
)


def test_redact_argv_preserves_command_shape_and_safe_refs() -> None:
    argv = [
        "dataset",
        "verify-access",
        "dataset:sciplex3",
        "--level",
        "public",
        "--license",
        "CC-BY-4.0",
        "--path",
        "/tmp/private/data.tsv",
        "--source",
        "https://example.org/data.tsv",
        "--note",
        "contains patient-sensitive notes",
    ]

    assert redact_argv(argv) == [
        "dataset",
        "verify-access",
        "dataset:sciplex3",
        "--level",
        "<value>",
        "--license",
        "<value:redacted>",
        "--path",
        "<path:redacted>",
        "--source",
        "<url:redacted>",
        "--note",
        "<value:redacted>",
    ]


def test_get_telemetry_dir_uses_environment_override(tmp_path: Path, monkeypatch) -> None:
    telemetry_dir = tmp_path / "telemetry"
    monkeypatch.setenv("SCIENCE_TELEMETRY_DIR", str(telemetry_dir))

    assert get_telemetry_dir() == telemetry_dir


def test_append_event_writes_monthly_jsonl_and_read_events_skips_malformed_rows(tmp_path: Path) -> None:
    event = new_event(
        event_type="command_finish",
        command="feedback list",
        argv=["feedback", "list", "--format", "json"],
        timestamp="2026-06-27T10:15:00-04:00",
        exit_code=0,
    )

    path = append_event(tmp_path, event)

    assert path == tmp_path / "events-2026-06.jsonl"
    assert path is not None
    path.write_text(path.read_text(encoding="utf-8") + "{not-json}\n", encoding="utf-8")
    rows = read_events(tmp_path)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "command_finish"
    assert rows[0]["command"] == "feedback list"
    assert rows[0]["argv_shape"] == ["feedback", "list", "--format", "<value>"]


def test_append_event_is_best_effort_for_unwritable_path(tmp_path: Path) -> None:
    file_path = tmp_path / "not-a-dir"
    file_path.write_text("content", encoding="utf-8")

    assert append_event(file_path, {"timestamp": "2026-06-27T10:15:00-04:00"}) is None


def test_summarize_events_counts_commands_errors_and_exit_codes() -> None:
    events = [
        {
            "event_type": "command_finish",
            "command": "feedback list",
            "exit_code": 0,
            "timestamp": "2026-06-27T10:15:00-04:00",
        },
        {
            "event_type": "command_error",
            "command": "feedback list",
            "exit_code": 2,
            "error_class": "NoSuchOption",
            "timestamp": "2026-06-27T10:16:00-04:00",
        },
        {
            "event_type": "command_finish",
            "command": "telemetry report",
            "exit_code": 0,
            "timestamp": "2026-06-27T10:17:00-04:00",
        },
    ]

    summary = summarize_events(events)

    assert summary == {
        "total_events": 3,
        "event_types": {"command_error": 1, "command_finish": 2},
        "commands": {"feedback list": 2, "telemetry report": 1},
        "error_classes": {"NoSuchOption": 1},
        "exit_codes": {"0": 2, "2": 1},
    }


def test_export_events_jsonl_is_sorted_and_deterministic() -> None:
    events = [
        {"event_id": "b", "timestamp": "2026-06-27T10:17:00-04:00", "event_type": "command_finish"},
        {"event_id": "a", "timestamp": "2026-06-27T10:15:00-04:00", "event_type": "command_finish"},
    ]

    output = export_events_jsonl(events)

    lines = output.splitlines()
    assert json.loads(lines[0])["event_id"] == "a"
    assert json.loads(lines[1])["event_id"] == "b"
    assert output.endswith("\n")


def test_prune_events_removes_rows_before_cutoff(tmp_path: Path) -> None:
    append_event(
        tmp_path,
        {
            "event_id": "old",
            "event_type": "command_finish",
            "timestamp": "2026-05-31T23:59:00-04:00",
        },
    )
    append_event(
        tmp_path,
        {
            "event_id": "new",
            "event_type": "command_finish",
            "timestamp": "2026-06-01T00:00:00-04:00",
        },
    )

    removed = prune_events(tmp_path, before=date(2026, 6, 1))

    assert removed == 1
    assert [event["event_id"] for event in read_events(tmp_path)] == ["new"]


def test_new_validation_summary_event_records_aggregate_failure_only() -> None:
    event = new_validation_summary_event(
        command="validate",
        profile="full",
        strict=False,
        fail_on=None,
        errors=1,
        warnings=2,
        infos=3,
        gated=True,
        rule_ids=["demo.error", "demo.warn", "demo.warn", None],
    )

    assert event["surface"] == "validation"
    assert event["event_type"] == "validation_summary"
    assert event["command"] == "validate"
    assert event["profile"] == "full"
    assert event["strict"] is False
    assert event["fail_on"] is None
    assert event["status"] == "fail"
    assert event["counts"] == {"error": 1, "warn": 2, "info": 3}
    assert event["top_checks"] == [{"check": "demo.warn", "count": 2}, {"check": "demo.error", "count": 1}]
    assert "path" not in event
    assert "message" not in event


def test_new_validation_summary_event_reports_warn_status() -> None:
    event = new_validation_summary_event(
        command="validate",
        profile="commit",
        strict=True,
        fail_on="ghost-files",
        errors=0,
        warnings=1,
        infos=0,
        gated=False,
        rule_ids=["demo.warn"],
    )

    assert event["status"] == "warn"
    assert event["counts"] == {"error": 0, "warn": 1, "info": 0}


def test_new_validation_summary_event_reports_pass_status() -> None:
    event = new_validation_summary_event(
        command="validate",
        profile="full",
        strict=False,
        fail_on=None,
        errors=0,
        warnings=0,
        infos=1,
        gated=False,
        rule_ids=[],
    )

    assert event["status"] == "pass"
    assert event["top_checks"] == []


def test_summarize_recent_for_feedback_target_matches_validate_events() -> None:
    events = [
        {
            "event_id": "error",
            "timestamp": "2026-06-27T10:00:00-04:00",
            "event_type": "command_error",
            "command": "validate",
            "error_class": "NoSuchOption",
        },
        {
            "event_id": "warn",
            "timestamp": "2026-06-27T10:01:00-04:00",
            "event_type": "validation_summary",
            "surface": "validation",
            "command": "validate",
            "status": "warn",
            "top_checks": [{"check": "demo.warn", "count": 2}],
        },
        {
            "event_id": "fail",
            "timestamp": "2026-06-27T10:02:00-04:00",
            "event_type": "validation_summary",
            "surface": "validation",
            "command": "validate",
            "status": "fail",
            "top_checks": [{"check": "demo.error", "count": 1}],
        },
        {
            "event_id": "unrelated",
            "timestamp": "2026-06-27T10:03:00-04:00",
            "event_type": "command_finish",
            "command": "feedback list",
        },
        {
            "event_id": "old",
            "timestamp": "2026-06-01T10:00:00-04:00",
            "event_type": "validation_summary",
            "surface": "validation",
            "command": "validate",
            "status": "fail",
            "top_checks": [{"check": "old.error", "count": 9}],
        },
    ]

    summary = summarize_recent_for_feedback_target(
        events,
        target="command:validate",
        today=date(2026, 6, 27),
        since_days=14,
    )

    assert summary["recent_events"] == 3
    assert summary["command_errors"] == {"NoSuchOption": 1}
    assert summary["commands"] == {"validate": 1}
    assert summary["validation"] == {
        "runs": 2,
        "statuses": {"fail": 1, "warn": 1},
        "top_checks": {"demo.error": 1, "demo.warn": 2},
    }


def test_format_feedback_telemetry_summarizes_validation_context() -> None:
    summary = {
        "recent_events": 2,
        "command_errors": {},
        "commands": {},
        "validation": {
            "runs": 2,
            "statuses": {"fail": 1, "warn": 1},
            "top_checks": {"demo.error": 1},
        },
    }

    assert format_feedback_telemetry(summary) == "validate: 2 runs, 1 fail, 1 warn"


def test_format_feedback_telemetry_reports_empty_context() -> None:
    assert format_feedback_telemetry({"recent_events": 0}) == "no recent telemetry"


def test_feedback_context_from_recent_event_selects_newest_eligible_event() -> None:
    events = [
        {
            "event_id": "pass-validation",
            "timestamp": "2026-06-27T10:00:00-04:00",
            "event_type": "validation_summary",
            "command": "validate",
            "status": "pass",
        },
        {
            "event_id": "older-error",
            "timestamp": "2026-06-27T10:01:00-04:00",
            "event_type": "command_error",
            "command": "dataset verify-access",
            "argv_shape": ["dataset", "verify-access", "dataset:sciplex3", "--source", "<url:redacted>"],
            "error_class": "ClickException",
        },
        {
            "event_id": "newer-validation",
            "timestamp": "2026-06-27T10:02:00-04:00",
            "event_type": "validation_summary",
            "surface": "validation",
            "command": "validate",
            "status": "warn",
            "counts": {"error": 0, "warn": 2, "info": 1},
            "top_checks": [{"check": "dataset.unstaged-deposit", "count": 2}],
        },
    ]

    context = feedback_context_from_recent_event(events, today=date(2026, 6, 27))

    assert context.event["event_id"] == "newer-validation"
    assert context.target == "command:validate"
    assert context.category == "gap"
    assert "Telemetry context:" in context.detail
    assert "- validation_status: warn" in context.detail
    assert "- validation_counts: error=0, warn=2, info=1" in context.detail
    assert "- top_checks: dataset.unstaged-deposit=2" in context.detail
    assert "<url:redacted>" not in context.detail


def test_feedback_context_from_recent_event_supports_one_based_index() -> None:
    events = [
        {
            "event_id": "old-error",
            "timestamp": "2026-06-27T10:00:00-04:00",
            "event_type": "command_error",
            "command": "feedback list",
            "error_class": "NoSuchOption",
        },
        {
            "event_id": "new-error",
            "timestamp": "2026-06-27T10:01:00-04:00",
            "event_type": "command_finish",
            "command": "dataset verify-access",
            "exit_code": 2,
        },
    ]

    context = feedback_context_from_recent_event(events, index=2, today=date(2026, 6, 27))

    assert context.event["event_id"] == "old-error"
    assert context.target == "command:feedback"
    assert context.category == "friction"
    assert "- error_class: NoSuchOption" in context.detail


def test_feedback_context_from_recent_event_rejects_empty_or_out_of_range_selection() -> None:
    events = [
        {
            "event_id": "old-error",
            "timestamp": "2026-06-01T10:00:00-04:00",
            "event_type": "command_error",
            "command": "feedback list",
        }
    ]

    try:
        feedback_context_from_recent_event(events, today=date(2026, 6, 27), since_days=14)
    except ValueError as exc:
        assert "No eligible recent telemetry events" in str(exc)
    else:
        raise AssertionError("Expected no recent telemetry error")

    try:
        feedback_context_from_recent_event(events, index=0, today=date(2026, 6, 27), since_days=60)
    except ValueError as exc:
        assert "1-based" in str(exc)
    else:
        raise AssertionError("Expected invalid index error")
