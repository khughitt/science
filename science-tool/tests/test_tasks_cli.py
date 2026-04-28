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
                ["tasks", "add", "My research task", "--priority", "P1"],
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

    def test_add_requires_priority(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "add", "No priority"])
            assert result.exit_code != 0

    def test_add_rejects_invalid_priority(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "add", "Bad prio", "--priority", "P9"])
            assert result.exit_code != 0

    def test_add_rejects_unknown_type_flag(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "add", "No type", "--type", "research", "--priority", "P1"])
            assert result.exit_code != 0


class TestTasksDone:
    def test_done_completes_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To complete", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "done", "t001"])
            assert result.exit_code == 0
            assert "done" in result.output.lower()

    def test_done_with_note(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To complete", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "done", "t001", "--note", "Finished early"])
            assert result.exit_code == 0

    def test_done_missing_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "done", "t999"])
            assert result.exit_code != 0


class TestTasksDefer:
    def test_defer_sets_deferred(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To defer", "--priority", "P2"])
            result = runner.invoke(main, ["tasks", "defer", "t001"])
            assert result.exit_code == 0
            assert "deferred" in result.output.lower()

    def test_defer_with_reason(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To defer", "--priority", "P2"])
            result = runner.invoke(main, ["tasks", "defer", "t001", "--reason", "Waiting for data"])
            assert result.exit_code == 0


class TestTasksBlock:
    def test_block_sets_blocked(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To block", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "block", "t001", "--by", "t002"])
            assert result.exit_code == 0
            assert "blocked" in result.output.lower()

    def test_block_requires_by(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To block", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "block", "t001"])
            assert result.exit_code != 0


class TestTasksUnblock:
    def test_unblock_clears_blockers(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Blocked", "--priority", "P1"])
            runner.invoke(main, ["tasks", "block", "t001", "--by", "t002"])
            result = runner.invoke(main, ["tasks", "unblock", "t001"])
            assert result.exit_code == 0
            assert "active" in result.output.lower()


class TestTasksEdit:
    def test_edit_priority(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To edit", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "edit", "t001", "--priority", "P0"])
            assert result.exit_code == 0

    def test_edit_status(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To edit", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "edit", "t001", "--status", "active"])
            assert result.exit_code == 0

    def test_edit_aspects(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path as _Path

            _Path("science.yaml").write_text("name: demo\nprofile: research\naspects: [hypothesis-testing]\n")
            runner.invoke(main, ["tasks", "add", "To edit", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "edit", "t001", "--aspects", "hypothesis-testing"])
            assert result.exit_code == 0, result.output

    def test_edit_related(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To edit", "--priority", "P1"])
            result = runner.invoke(
                main, ["tasks", "edit", "t001", "--related", "hypothesis:h01", "--related", "topic:rna"]
            )
            assert result.exit_code == 0

    def test_edit_archived_description(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            (tasks_dir / "done").mkdir(parents=True)
            (tasks_dir / "active.md").write_text("")
            archived_path = tasks_dir / "done" / "2026-04.md"
            archived_path.write_text(
                "## [t141] Archived task\n"
                "- priority: P1\n"
                "- status: done\n"
                "- created: 2026-04-01\n"
                "- completed: 2026-04-02\n"
                "\n"
                "Archived details.\n"
            )

            result = runner.invoke(main, ["tasks", "edit", "t141", "--description", "Corrected details."])

            assert result.exit_code == 0, result.output
            assert "Corrected details." in archived_path.read_text()

    def test_edit_archived_rejects_non_closed_status(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            (tasks_dir / "done").mkdir(parents=True)
            (tasks_dir / "active.md").write_text("")
            archived_path = tasks_dir / "done" / "2026-04.md"
            archived_path.write_text(
                "## [t141] Archived task\n"
                "- priority: P1\n"
                "- status: done\n"
                "- created: 2026-04-01\n"
                "- completed: 2026-04-02\n"
                "\n"
                "Archived details.\n"
            )

            result = runner.invoke(main, ["tasks", "edit", "t141", "--status", "active"])

            assert result.exit_code != 0
            assert "Cannot set archived task t141 to non-closed status 'active'" in result.output
            assert "- status: done" in archived_path.read_text()


class TestTasksNote:
    def test_note_appends_to_active_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            runner.invoke(main, ["tasks", "add", "Needs note", "--priority", "P1"])

            result = runner.invoke(main, ["tasks", "note", "t001", "Clarified scope.", "--date", "2026-04-28"])

            assert result.exit_code == 0, result.output
            assert "Added note to [t001] (2026-04-28)" in result.output
            body = Path("tasks/active.md").read_text()
            assert "### Notes" in body
            assert "- 2026-04-28: Clarified scope." in body

    def test_note_appends_to_archived_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            (tasks_dir / "done").mkdir(parents=True)
            (tasks_dir / "active.md").write_text("")
            archived_path = tasks_dir / "done" / "2026-04.md"
            archived_path.write_text(
                "## [t141] Archived task\n"
                "- priority: P1\n"
                "- status: done\n"
                "- created: 2026-04-01\n"
                "- completed: 2026-04-02\n"
                "\n"
                "Archived details.\n"
            )

            result = runner.invoke(
                main, ["tasks", "note", "t141", "Archived clarification.", "--date", "2026-04-28"]
            )

            assert result.exit_code == 0, result.output
            assert "Added note to [t141] (2026-04-28)" in result.output
            assert "- 2026-04-28: Archived clarification." in archived_path.read_text()

    def test_note_rejects_blank_note(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Needs note", "--priority", "P1"])

            result = runner.invoke(main, ["tasks", "note", "t001", "   ", "--date", "2026-04-28"])

            assert result.exit_code != 0
            assert "Task note cannot be empty" in result.output

    def test_note_rejects_invalid_date(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Needs note", "--priority", "P1"])

            result = runner.invoke(main, ["tasks", "note", "t001", "Clarified.", "--date", "not-a-date"])

            assert result.exit_code != 0
            assert "Date must use YYYY-MM-DD" in result.output


class TestTasksList:
    def test_list_empty(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "list"])
            assert result.exit_code == 0

    def test_list_shows_tasks(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Task A", "--priority", "P1"])
            runner.invoke(main, ["tasks", "add", "Task B", "--priority", "P2"])
            result = runner.invoke(main, ["tasks", "list"])
            assert result.exit_code == 0
            assert "Task A" in result.output
            assert "Task B" in result.output

    def test_list_rejects_type_flag(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "list", "--type", "dev"])
            assert result.exit_code != 0

    def test_list_filter_aspect(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            Path("science.yaml").write_text(
                "name: demo\nprofile: research\naspects: [hypothesis-testing, software-development]\n"
            )
            tasks_dir = Path("tasks")
            tasks_dir.mkdir()
            (tasks_dir / "active.md").write_text(
                "## [t001] Dev task\n"
                "- priority: P1\n"
                "- status: proposed\n"
                "- aspects: [software-development]\n"
                "- created: 2026-03-01\n\nDev.\n\n"
                "## [t002] Research task\n"
                "- priority: P2\n"
                "- status: proposed\n"
                "- aspects: [hypothesis-testing]\n"
                "- created: 2026-03-02\n\nRes.\n"
            )
            result = runner.invoke(main, ["tasks", "list", "--aspect", "software-development"])
            assert result.exit_code == 0, result.output
            assert "Dev task" in result.output
            assert "Research task" not in result.output

    def test_list_hides_done_by_default(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            # Manually write a file with both open and done tasks
            tasks_dir = Path("tasks")
            tasks_dir.mkdir()
            (tasks_dir / "active.md").write_text(
                "## [t001] Open task\n- type: dev\n- priority: P1\n- status: proposed\n- created: 2026-03-01\n\nOpen.\n\n"
                "## [t002] Done task\n- type: dev\n- priority: P2\n- status: done\n- created: 2026-03-02\n- completed: 2026-03-05\n\nDone.\n"
            )
            result = runner.invoke(main, ["tasks", "list"])
            assert result.exit_code == 0
            assert "Open task" in result.output
            assert "Done task" not in result.output

    def test_list_all_shows_done(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            tasks_dir.mkdir()
            (tasks_dir / "active.md").write_text(
                "## [t001] Open task\n- type: dev\n- priority: P1\n- status: proposed\n- created: 2026-03-01\n\nOpen.\n\n"
                "## [t002] Done task\n- type: dev\n- priority: P2\n- status: done\n- created: 2026-03-02\n- completed: 2026-03-05\n\nDone.\n"
            )
            result = runner.invoke(main, ["tasks", "list", "--all"])
            assert result.exit_code == 0
            assert "Open task" in result.output
            assert "Done task" in result.output

    def test_list_status_done_filter(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            tasks_dir.mkdir()
            (tasks_dir / "active.md").write_text(
                "## [t001] Open task\n- type: dev\n- priority: P1\n- status: proposed\n- created: 2026-03-01\n\nOpen.\n\n"
                "## [t002] Done task\n- type: dev\n- priority: P2\n- status: done\n- created: 2026-03-02\n- completed: 2026-03-05\n\nDone.\n"
            )
            result = runner.invoke(main, ["tasks", "list", "--status", "done"])
            assert result.exit_code == 0
            assert "Done task" in result.output
            assert "Open task" not in result.output

    def test_list_json_format(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "JSON task", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "list", "--format", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert len(data["rows"]) == 1
            assert data["rows"][0]["title"] == "JSON task"


class TestTasksShow:
    def test_show_displays_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Show me", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "show", "t001"])
            assert result.exit_code == 0
            assert "Show me" in result.output
            assert "t001" in result.output

    def test_show_missing_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "show", "t999"])
            assert result.exit_code != 0

    def test_show_displays_archived_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            (tasks_dir / "done").mkdir(parents=True)
            (tasks_dir / "active.md").write_text("")
            (tasks_dir / "done" / "2026-04.md").write_text(
                "## [t141] Archived task\n"
                "- priority: P1\n"
                "- status: done\n"
                "- created: 2026-04-01\n"
                "- completed: 2026-04-02\n"
                "\n"
                "Archived details.\n"
            )

            result = runner.invoke(main, ["tasks", "show", "t141"])

            assert result.exit_code == 0, result.output
            assert "Archived task" in result.output
            assert "Archived details." in result.output

    def test_show_missing_task_mentions_archives(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            (tasks_dir / "done").mkdir(parents=True)
            (tasks_dir / "active.md").write_text("")
            (tasks_dir / "done" / "2026-04.md").write_text("")

            result = runner.invoke(main, ["tasks", "show", "t999"])

            assert result.exit_code != 0
            assert "tasks/done/*.md" in result.output
            assert "2026-04.md" in result.output


class TestTasksRetire:
    def test_retire_sets_retired(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To retire", "--priority", "P2"])
            result = runner.invoke(main, ["tasks", "retire", "t001"])
            assert result.exit_code == 0
            assert "retired" in result.output.lower()

    def test_retire_with_reason(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To retire", "--priority", "P2"])
            result = runner.invoke(main, ["tasks", "retire", "t001", "--reason", "No longer relevant"])
            assert result.exit_code == 0

    def test_retire_missing_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "retire", "t999"])
            assert result.exit_code != 0


class TestTasksGroups:
    def test_add_with_group(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(
                main,
                ["tasks", "add", "Grouped", "--priority", "P1", "--group", "visualization"],
            )
            assert result.exit_code == 0

    def test_edit_group(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To edit", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "edit", "t001", "--group", "my-group"])
            assert result.exit_code == 0

    def test_list_by_related(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "T1", "--priority", "P1", "--related", "topic:alpha"])
            runner.invoke(main, ["tasks", "add", "T2", "--priority", "P2", "--related", "topic:beta"])
            result = runner.invoke(main, ["tasks", "list", "--related", "alpha"])
            assert result.exit_code == 0
            assert "T1" in result.output
            assert "T2" not in result.output

    def test_list_by_group(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "T1", "--priority", "P1", "--group", "lens"])
            runner.invoke(main, ["tasks", "add", "T2", "--priority", "P2", "--group", "formula"])
            result = runner.invoke(main, ["tasks", "list", "--group", "lens"])
            assert result.exit_code == 0
            assert "T1" in result.output
            assert "T2" not in result.output

    def test_edit_status_retired(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To retire", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "edit", "t001", "--status", "retired"])
            assert result.exit_code == 0


class TestTasksSummary:
    def test_summary_empty(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "summary"])
            assert result.exit_code == 0

    def test_summary_with_tasks(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "T1", "--priority", "P1"])
            runner.invoke(main, ["tasks", "add", "T2", "--priority", "P2"])
            runner.invoke(main, ["tasks", "add", "T3", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "summary"])
            assert result.exit_code == 0
            assert "proposed" in result.output.lower()


def test_tasks_add_accepts_aspects_flag(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "tasks").mkdir()
    (tmp_path / "science.yaml").write_text("name: demo\nprofile: research\naspects: [hypothesis-testing]\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "tasks",
            "add",
            "Demo task",
            "--priority",
            "P1",
            "--aspects",
            "hypothesis-testing",
        ],
    )
    assert result.exit_code == 0, result.output
    body = (tmp_path / "tasks" / "active.md").read_text()
    assert "- aspects: [hypothesis-testing]" in body


def test_tasks_add_without_type_or_aspects(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "tasks").mkdir()
    (tmp_path / "science.yaml").write_text("name: demo\nprofile: research\naspects: [hypothesis-testing]\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["tasks", "add", "Demo", "--priority", "P2"])
    assert result.exit_code == 0, result.output
    body = (tmp_path / "tasks" / "active.md").read_text()
    assert "aspects" not in body
    assert "- type:" not in body


def test_tasks_edit_updates_aspects(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "tasks").mkdir()
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\naspects: [hypothesis-testing, software-development]\n"
    )
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Demo\n- priority: P1\n- status: proposed\n- created: 2026-04-19\n\nBody.\n"
    )
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "tasks",
            "edit",
            "t001",
            "--aspects",
            "software-development",
        ],
    )
    assert result.exit_code == 0, result.output
    body = (tmp_path / "tasks" / "active.md").read_text()
    assert "- aspects: [software-development]" in body


def test_tasks_list_filter_by_aspect(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "tasks").mkdir()
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\naspects: [hypothesis-testing, software-development]\n"
    )
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Research task\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- aspects: [hypothesis-testing]\n"
        "- created: 2026-04-19\n"
        "\n"
        "Body.\n"
        "\n"
        "## [t002] Software task\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- aspects: [software-development]\n"
        "- created: 2026-04-19\n"
        "\n"
        "Body.\n"
    )
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["tasks", "list", "--aspect", "hypothesis-testing"])
    assert result.exit_code == 0, result.output
    assert "t001" in result.output
    assert "t002" not in result.output
