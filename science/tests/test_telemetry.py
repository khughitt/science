"""Tests for local-first telemetry storage and reporting."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from science_tool.telemetry import (
    append_event,
    export_events_jsonl,
    get_telemetry_dir,
    new_event,
    prune_events,
    read_events,
    redact_argv,
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
