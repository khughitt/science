"""Tests for the tasks CLI command group."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from science_tool.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestTasksAdd:
    def test_add_creates_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(
                main,
                ["tasks", "add", "My research task", "--type", "research", "--priority", "P1"],
            )
            assert result.exit_code == 0
            assert "t001" in result.output
            assert "My research task" in result.output

    def test_add_with_description(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(
                main,
                [
                    "tasks",
                    "add",
                    "Task with desc",
                    "--type",
                    "dev",
                    "--priority",
                    "P2",
                    "--description",
                    "Some details",
                ],
            )
            assert result.exit_code == 0
            assert "t001" in result.output

    def test_add_with_related_and_blocked_by(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(
                main,
                [
                    "tasks",
                    "add",
                    "Blocked task",
                    "--type",
                    "dev",
                    "--priority",
                    "P0",
                    "--related",
                    "t001",
                    "--related",
                    "t002",
                    "--blocked-by",
                    "t001",
                ],
            )
            assert result.exit_code == 0
            assert "t001" in result.output

    def test_add_requires_type(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "add", "No type", "--priority", "P1"])
            assert result.exit_code != 0

    def test_add_requires_priority(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "add", "No priority", "--type", "dev"])
            assert result.exit_code != 0

    def test_add_rejects_invalid_type(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "add", "Bad type", "--type", "invalid", "--priority", "P1"])
            assert result.exit_code != 0

    def test_add_rejects_invalid_priority(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "add", "Bad prio", "--type", "dev", "--priority", "P9"])
            assert result.exit_code != 0


class TestTasksDone:
    def test_done_completes_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To complete", "--type", "dev", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "done", "t001"])
            assert result.exit_code == 0
            assert "done" in result.output.lower()

    def test_done_with_note(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To complete", "--type", "dev", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "done", "t001", "--note", "Finished early"])
            assert result.exit_code == 0

    def test_done_missing_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "done", "t999"])
            assert result.exit_code != 0


class TestTasksDefer:
    def test_defer_sets_deferred(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To defer", "--type", "research", "--priority", "P2"])
            result = runner.invoke(main, ["tasks", "defer", "t001"])
            assert result.exit_code == 0
            assert "deferred" in result.output.lower()

    def test_defer_with_reason(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To defer", "--type", "research", "--priority", "P2"])
            result = runner.invoke(main, ["tasks", "defer", "t001", "--reason", "Waiting for data"])
            assert result.exit_code == 0


class TestTasksBlock:
    def test_block_sets_blocked(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To block", "--type", "dev", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "block", "t001", "--by", "t002"])
            assert result.exit_code == 0
            assert "blocked" in result.output.lower()

    def test_block_requires_by(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To block", "--type", "dev", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "block", "t001"])
            assert result.exit_code != 0


class TestTasksUnblock:
    def test_unblock_clears_blockers(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Blocked", "--type", "dev", "--priority", "P1"])
            runner.invoke(main, ["tasks", "block", "t001", "--by", "t002"])
            result = runner.invoke(main, ["tasks", "unblock", "t001"])
            assert result.exit_code == 0
            assert "active" in result.output.lower()


class TestTasksEdit:
    def test_edit_priority(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To edit", "--type", "dev", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "edit", "t001", "--priority", "P0"])
            assert result.exit_code == 0

    def test_edit_status(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To edit", "--type", "dev", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "edit", "t001", "--status", "active"])
            assert result.exit_code == 0

    def test_edit_type(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To edit", "--type", "dev", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "edit", "t001", "--type", "research"])
            assert result.exit_code == 0

    def test_edit_rejects_invalid_status(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To edit", "--type", "dev", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "edit", "t001", "--status", "invalid"])
            assert result.exit_code != 0


class TestTasksList:
    def test_list_empty(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "list"])
            assert result.exit_code == 0

    def test_list_shows_tasks(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Task A", "--type", "dev", "--priority", "P1"])
            runner.invoke(main, ["tasks", "add", "Task B", "--type", "research", "--priority", "P2"])
            result = runner.invoke(main, ["tasks", "list"])
            assert result.exit_code == 0
            assert "Task A" in result.output
            assert "Task B" in result.output

    def test_list_filter_type(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Dev task", "--type", "dev", "--priority", "P1"])
            runner.invoke(main, ["tasks", "add", "Research task", "--type", "research", "--priority", "P2"])
            result = runner.invoke(main, ["tasks", "list", "--type", "dev"])
            assert result.exit_code == 0
            assert "Dev task" in result.output
            assert "Research task" not in result.output

    def test_list_json_format(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "JSON task", "--type", "dev", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "list", "--format", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert len(data["rows"]) == 1
            assert data["rows"][0]["title"] == "JSON task"


class TestTasksShow:
    def test_show_displays_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Show me", "--type", "dev", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "show", "t001"])
            assert result.exit_code == 0
            assert "Show me" in result.output
            assert "t001" in result.output

    def test_show_missing_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "show", "t999"])
            assert result.exit_code != 0


class TestTasksSummary:
    def test_summary_empty(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "summary"])
            assert result.exit_code == 0

    def test_summary_with_tasks(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "T1", "--type", "dev", "--priority", "P1"])
            runner.invoke(main, ["tasks", "add", "T2", "--type", "research", "--priority", "P2"])
            runner.invoke(main, ["tasks", "add", "T3", "--type", "dev", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "summary"])
            assert result.exit_code == 0
            assert "proposed" in result.output.lower()
