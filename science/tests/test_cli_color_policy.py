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
