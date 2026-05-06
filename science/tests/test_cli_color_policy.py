from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _write_active_tasks() -> None:
    tasks_dir = Path("tasks")
    tasks_dir.mkdir()
    (tasks_dir / "active.md").write_text(
        "## [t001] Color task\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- related: [question:q001-demo, custom-kind:alpha]\n"
        "- created: 2026-05-01\n\n"
        "Description.\n"
    )


def test_root_color_rejects_invalid_policy() -> None:
    result = CliRunner().invoke(main, ["--color", "sometimes", "tasks", "list"])

    assert result.exit_code != 0
    assert "Invalid value for '--color'" in result.output


def test_tasks_list_default_has_no_ansi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)

    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["tasks", "list"])

    assert result.exit_code == 0, result.output
    assert "Color task" in result.output
    assert ANSI_RE.search(result.output) is None


def test_tasks_list_auto_has_no_ansi_under_clirunner() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["--color", "auto", "tasks", "list"])

    assert result.exit_code == 0, result.output
    assert "Color task" in result.output
    assert ANSI_RE.search(result.output) is None


def test_tasks_list_always_emits_ansi() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["--color", "always", "tasks", "list"])

    assert result.exit_code == 0, result.output
    assert "Color task" in result.output
    assert ANSI_RE.search(result.output) is not None


def test_tasks_list_json_has_no_ansi_even_when_color_forced() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["--color", "always", "tasks", "list", "--format", "json"])

    assert result.exit_code == 0, result.output
    assert ANSI_RE.search(result.output) is None
    payload = json.loads(result.output)
    assert payload["rows"][0]["title"] == "Color task"


def test_emit_query_rows_default_has_no_ansi(capsys) -> None:
    from science_tool.output import emit_query_rows

    emit_query_rows(
        output_format="table",
        title="Rows",
        columns=[("id", "ID"), ("title", "Title")],
        rows=[{"id": "question:q001-demo", "title": "Demo"}],
    )

    captured = capsys.readouterr()
    assert "question:q001-demo" in captured.out
    assert ANSI_RE.search(captured.out) is None


def _health_report_with_archive_lag() -> dict:
    return {
        "archive_lag": {
            "done_in_active": 1,
            "retired_in_active": 0,
            "missing_completed": 0,
        },
        "managed_artifacts": [],
        "tooling_scaffold": [],
        "unregistered_ref_kinds": [],
        "unresolved_refs": [],
        "lingering_tags_lines": [],
        "identity_policy": [],
        "legacy_structured_literature_prefixes": [],
        "dataset_anomalies": [],
        "layered_claims": {
            "migration_issues": [],
            "rival_model_packets_missing_discriminating_predictions": [],
            "proposition_claim_layer_coverage": {
                "numerator": 0,
                "denominator": 0,
                "fraction": 1.0,
            },
            "causal_leaning_identification_coverage": {
                "numerator": 0,
                "denominator": 0,
                "fraction": 1.0,
            },
        },
    }


def test_health_never_strips_markup_and_ansi(monkeypatch) -> None:
    from science_tool.graph import health as health_module

    monkeypatch.setattr(health_module, "build_health_report", lambda _root: _health_report_with_archive_lag())

    result = CliRunner().invoke(main, ["--color", "never", "health"])

    assert result.exit_code == 0, result.output
    assert "Next:" in result.output
    assert "science tasks archive" in result.output
    assert "[cyan]" not in result.output
    assert ANSI_RE.search(result.output) is None


def test_health_always_emits_ansi(monkeypatch) -> None:
    from science_tool.graph import health as health_module

    monkeypatch.setattr(health_module, "build_health_report", lambda _root: _health_report_with_archive_lag())

    result = CliRunner().invoke(main, ["--color", "always", "health"])

    assert result.exit_code == 0, result.output
    assert "science tasks archive" in result.output
    assert ANSI_RE.search(result.output) is not None


def test_force_color_enables_color_when_flag_omitted(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["tasks", "list"])

    assert result.exit_code == 0, result.output
    assert ANSI_RE.search(result.output) is not None


def test_no_color_beats_force_color_when_flag_omitted(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("NO_COLOR", "1")
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["tasks", "list"])

    assert result.exit_code == 0, result.output
    assert ANSI_RE.search(result.output) is None


def test_explicit_color_beats_no_color(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setenv("NO_COLOR", "1")
    with runner.isolated_filesystem():
        _write_active_tasks()

        result = runner.invoke(main, ["--color", "always", "tasks", "list"])

    assert result.exit_code == 0, result.output
    assert ANSI_RE.search(result.output) is not None
