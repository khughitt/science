"""Tests for the tasks CLI command group."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from click.testing import CliRunner
from science_model.tasks import Task

from science_tool import tasks as task_module
from science_tool.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_tasks_archive_is_not_a_command(runner: CliRunner) -> None:
    result = runner.invoke(main, ["tasks", "archive"])

    assert result.exit_code == 2
    assert "No such command 'archive'" in result.output


def _write_active_task(
    root: Path,
    *,
    task_id: str,
    title: str,
    priority: str = "P1",
    status: str = "proposed",
    task_type: str = "",
    aspects: list[str] | None = None,
    blocked_by: list[str] | None = None,
    created: date = date(2026, 3, 1),
    description: str = "Body.",
) -> Path:
    task = Task(
        id=task_id,
        title=title,
        type=task_type,
        priority=priority,
        status=status,
        aspects=aspects or [],
        blocked_by=blocked_by or [],
        created=created,
        description=description,
    )
    path = root / "tasks" / "active" / f"{task_id}-{title.lower().replace(' ', '-')}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(task_module.render_task_file(task), encoding="utf-8")
    return path


def _active_task_path(root: Path, task_id: str) -> Path:
    matches = list((root / "tasks" / "active").glob(f"{task_id}-*.md"))
    matches.extend((root / "tasks" / "active").glob(f"{task_id}.md"))
    assert len(matches) == 1
    return matches[0]


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
    def test_block_requires_by(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To block", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "block", "t001"])
            assert result.exit_code != 0


class TestTasksUnblock:
    def test_unblock_clears_blockers(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Blocked", "--priority", "P1"])
            block_result = runner.invoke(main, ["tasks", "block", "t001", "--by", "task:t002", "--force"])
            assert block_result.exit_code == 0, block_result.output
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
            (tasks_dir / "active").mkdir()
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
            (tasks_dir / "active").mkdir()
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
            body = _active_task_path(Path(), "t001").read_text()
            assert "### Notes" in body
            assert "- 2026-04-28: Clarified scope." in body

    def test_note_appends_to_archived_task(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            tasks_dir = Path("tasks")
            (tasks_dir / "done").mkdir(parents=True)
            (tasks_dir / "active").mkdir()
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

            result = runner.invoke(main, ["tasks", "note", "t141", "Archived clarification.", "--date", "2026-04-28"])

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
            result = runner.invoke(main, ["tasks", "list", "--status", "proposed"])
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
            _write_active_task(
                Path(),
                task_id="t001",
                title="Dev task",
                aspects=["software-development"],
                description="Dev.",
            )
            _write_active_task(
                Path(),
                task_id="t002",
                title="Research task",
                priority="P2",
                aspects=["hypothesis-testing"],
                created=date(2026, 3, 2),
                description="Res.",
            )
            result = runner.invoke(
                main,
                ["tasks", "list", "--status", "proposed", "--aspect", "software-development"],
            )
            assert result.exit_code == 0, result.output
            assert "Dev task" in result.output
            assert "Research task" not in result.output

    def test_list_hides_done_by_default(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            from pathlib import Path

            _write_active_task(
                Path(),
                task_id="t001",
                title="Open task",
                status="active",
                task_type="dev",
                description="Open.",
            )
            result = runner.invoke(main, ["tasks", "list"])
            assert result.exit_code == 0
            assert "Open task" in result.output
            assert "Done task" not in result.output

    def test_list_all_shows_non_working_active_statuses(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            today = date.today()
            _write_active_task(Path(), task_id="t001", title="Proposed task", task_type="dev")
            _write_active_task(
                Path(),
                task_id="t002",
                title="Deferred task",
                priority="P2",
                status="deferred",
                task_type="dev",
                created=date(2026, 3, 2),
            )
            done = Path("tasks/done") / f"{today:%Y-%m}.md"
            done.parent.mkdir()
            done.write_text(
                "## [t003] Archived task\n"
                "- priority: P1\n"
                "- status: done\n"
                "- aspects: []\n"
                f"- created: {today.isoformat()}\n"
                f"- completed: {today.isoformat()}\n\n"
                "Archived.\n",
                encoding="utf-8",
            )
            result = runner.invoke(main, ["tasks", "list", "--all"])
            assert result.exit_code == 0
            assert "Proposed task" in result.output
            assert "Deferred task" in result.output
            assert "Archived task" not in result.output

    @pytest.mark.parametrize("status", ["done", "retired"])
    def test_list_closed_status_requires_since(self, runner: CliRunner, status: str) -> None:
        with runner.isolated_filesystem():
            _write_active_task(Path(), task_id="t001", title="Open task", task_type="dev")
            result = runner.invoke(main, ["tasks", "list", "--status", status])
            assert result.exit_code != 0
            assert f"--status {status}" in result.output
            assert "--since YYYY-MM-DD" in result.output

    def test_list_reports_duplicate_active_and_done_task_sources_without_traceback(
        self,
        runner: CliRunner,
    ) -> None:
        today = date.today()
        with runner.isolated_filesystem():
            _write_active_task(
                Path(),
                task_id="t001",
                title="Active task",
                created=today,
                description="Active.",
            )
            done = Path("tasks/done") / f"{today:%Y-%m}.md"
            done.parent.mkdir()
            done.write_text(
                "## [t001] Done task\n"
                "- priority: P1\n"
                "- status: done\n"
                "- aspects: []\n"
                f"- created: {today.isoformat()}\n"
                f"- completed: {today.isoformat()}\n\n"
                "Done.\n",
                encoding="utf-8",
            )

            result = runner.invoke(
                main,
                ["tasks", "list", "--since", today.isoformat()],
            )
            assert result.exit_code != 0
            assert "entity 'task:t001' produced by multiple sources" in result.output
            assert "Traceback" not in result.output

    def test_list_json_format(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "JSON task", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "list", "--status", "proposed", "--format", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert len(data["rows"]) == 1
            assert data["rows"][0]["title"] == "JSON task"

    def test_list_json_includes_meta(self, runner: CliRunner) -> None:
        """fb-2026-05-01-006: JSON output exposes counts, sort order, and applied filters
        so callers can tell whether they're seeing the full list or a curated view."""
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "Active task", "--priority", "P1"])
            runner.invoke(main, ["tasks", "add", "Other task", "--priority", "P2"])
            runner.invoke(main, ["tasks", "edit", "t001", "--status", "active"])
            runner.invoke(main, ["tasks", "edit", "t002", "--status", "active"])
            # Filtered view: only P1
            result = runner.invoke(main, ["tasks", "list", "--format", "json", "--priority", "P1"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            meta = data["meta"]
            assert meta["active_total"] == 2
            assert meta["returned_count"] == 1
            assert meta["sort_order"] == "status_rank,id"
            assert meta["applied_filters"]["priority"] == "P1"
            # Default working set surfaces under applied_filters too.
            assert meta["applied_filters"]["only_status"] == ["active", "blocked"]

    def test_list_since_rejects_non_terminal_status(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(
                main, ["tasks", "list", "--since", "2026-01-01", "--status", "active"]
            )
            assert result.exit_code != 0
            assert "--since only applies to closed tasks" in result.output

    def test_list_since_rejects_invalid_date(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["tasks", "list", "--since", "not-a-date"])
            assert result.exit_code != 0
            assert "YYYY-MM-DD" in result.output

    def test_list_since_returns_only_closed_tasks_on_or_after_date(self, runner: CliRunner) -> None:
        from datetime import date

        today = date.today()
        since = today.replace(day=1)
        month_str = today.strftime("%Y-%m")
        with runner.isolated_filesystem():
            tasks_dir = Path("tasks")
            done_dir = tasks_dir / "done"
            done_dir.mkdir(parents=True)
            _write_active_task(
                Path(),
                task_id="t001",
                title="Still open",
                status="active",
                task_type="dev",
                created=date(2026, 1, 1),
                description="Open, no completed date.",
            )
            (done_dir / f"{month_str}.md").write_text(
                "## [t002] Closed after since\n"
                "- type: dev\n- priority: P1\n- status: done\n"
                f"- created: 2026-01-01\n- completed: {today.isoformat()}\n\nClosed.\n"
            )
            result = runner.invoke(
                main, ["tasks", "list", "--since", since.isoformat(), "--format", "json"]
            )
            assert result.exit_code == 0, result.output
            data = json.loads(result.output)
            ids = {row["id"] for row in data["rows"]}
            assert ids == {"t002"}
            # --since queries every status, so the working-set-only marker
            # must not be present in the applied-filters meta.
            assert "only_status" not in data["meta"]["applied_filters"]
            # active_total counts only active/ and is meaningless for a
            # --since query spanning monthly done ledgers -- it must be omitted.
            assert "active_total" not in data["meta"]

            status_result = runner.invoke(
                main,
                [
                    "tasks",
                    "list",
                    "--status",
                    "done",
                    "--since",
                    since.isoformat(),
                ],
            )
            assert status_result.exit_code == 0, status_result.output
            assert "Closed after since" in status_result.output
            assert "Still open" not in status_result.output

    def test_list_since_respects_output_sink(self, runner: CliRunner, tmp_path: Path) -> None:
        from datetime import date

        today = date.today()
        since = today.replace(day=1)
        month_str = today.strftime("%Y-%m")
        with runner.isolated_filesystem():
            tasks_dir = Path("tasks")
            done_dir = tasks_dir / "done"
            done_dir.mkdir(parents=True)
            (done_dir / f"{month_str}.md").write_text(
                "## [t002] Closed after since\n"
                "- type: dev\n- priority: P1\n- status: done\n"
                f"- created: 2026-01-01\n- completed: {today.isoformat()}\n\nClosed.\n"
            )
            output_path = tmp_path / "out.json"
            result = runner.invoke(
                main,
                [
                    "tasks",
                    "list",
                    "--since",
                    since.isoformat(),
                    "--format",
                    "json",
                    "--output",
                    str(output_path),
                ],
            )
            assert result.exit_code == 0, result.output
            assert output_path.exists()
            data = json.loads(output_path.read_text())
            ids = {row["id"] for row in data["rows"]}
            assert ids == {"t002"}


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
            (tasks_dir / "active").mkdir()
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
            (tasks_dir / "active").mkdir()
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
            result = runner.invoke(main, ["tasks", "list", "--status", "proposed", "--related", "alpha"])
            assert result.exit_code == 0
            assert "T1" in result.output
            assert "T2" not in result.output

    def test_list_by_group(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "T1", "--priority", "P1", "--group", "lens"])
            runner.invoke(main, ["tasks", "add", "T2", "--priority", "P2", "--group", "formula"])
            result = runner.invoke(main, ["tasks", "list", "--status", "proposed", "--group", "lens"])
            assert result.exit_code == 0
            assert "T1" in result.output
            assert "T2" not in result.output

    def test_edit_status_retired_requires_terminal_command(self, runner: CliRunner) -> None:
        with runner.isolated_filesystem():
            runner.invoke(main, ["tasks", "add", "To retire", "--priority", "P1"])
            result = runner.invoke(main, ["tasks", "edit", "t001", "--status", "retired"])
            assert result.exit_code != 0
            assert "use science tasks done/retire to close a task" in result.output


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
    task = task_module.parse_task_file(_active_task_path(tmp_path, "t001"))
    assert task.aspects == ["hypothesis-testing"]


def test_tasks_add_accepts_task_scoped_aspect_when_project_aspects_absent(
    tmp_path, monkeypatch
):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "tasks").mkdir()
    (tmp_path / "science.yaml").write_text("name: demo\nprofile: research\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "tasks",
            "add",
            "Inspect analysis inputs",
            "--priority",
            "P1",
            "--aspects",
            "computational-analysis",
        ],
    )
    assert result.exit_code == 0, result.output
    task = task_module.parse_task_file(_active_task_path(tmp_path, "t001"))
    assert task.aspects == ["computational-analysis"]


def test_tasks_add_without_type_or_aspects(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "tasks").mkdir()
    (tmp_path / "science.yaml").write_text("name: demo\nprofile: research\naspects: [hypothesis-testing]\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["tasks", "add", "Demo", "--priority", "P2"])
    assert result.exit_code == 0, result.output
    task = task_module.parse_task_file(_active_task_path(tmp_path, "t001"))
    # aspects is validate-required, so add without --aspects still emits '[]'
    # (feedback fb-2026-05-30-005); only type stays omitted when empty.
    assert task.aspects == []
    assert task.type == ""


def test_tasks_edit_updates_aspects(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\naspects: [hypothesis-testing, software-development]\n"
    )
    _write_active_task(
        tmp_path,
        task_id="t001",
        title="Demo",
        created=date(2026, 4, 19),
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
    task = task_module.parse_task_file(_active_task_path(tmp_path, "t001"))
    assert task.aspects == ["software-development"]


def test_tasks_edit_accepts_task_scoped_aspect_when_project_aspects_absent(
    tmp_path, monkeypatch
):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "science.yaml").write_text("name: demo\nprofile: research\n")
    _write_active_task(
        tmp_path,
        task_id="t001",
        title="Demo",
        created=date(2026, 4, 19),
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
            "computational-analysis",
        ],
    )
    assert result.exit_code == 0, result.output
    task = task_module.parse_task_file(_active_task_path(tmp_path, "t001"))
    assert task.aspects == ["computational-analysis"]


def test_tasks_list_filter_by_aspect(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\naspects: [hypothesis-testing, software-development]\n"
    )
    _write_active_task(
        tmp_path,
        task_id="t001",
        title="Research task",
        aspects=["hypothesis-testing"],
        created=date(2026, 4, 19),
    )
    _write_active_task(
        tmp_path,
        task_id="t002",
        title="Software task",
        aspects=["software-development"],
        created=date(2026, 4, 19),
    )
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["tasks", "list", "--status", "proposed", "--aspect", "hypothesis-testing"],
    )
    assert result.exit_code == 0, result.output
    assert "t001" in result.output
    assert "t002" not in result.output


# ---------------------------------------------------------------------------
# Typed-blocker CLI tests (Task 8)
# ---------------------------------------------------------------------------

from _fixtures.entity_helpers import seed_project  # noqa: E402


def _write_dp(tmp_path: Path, slug: str) -> None:
    dp_dir = tmp_path / "data" / slug
    dp_dir.mkdir(parents=True, exist_ok=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        f"id: dataset:{slug}\n"
        "kind: dataset\n"
        f"title: {slug.capitalize()}\n"
        "status: active\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        "access: {level: public, verified: true}\n",
        encoding="utf-8",
    )


def _write_split_legacy_blocker(tmp_path: Path, *, task_id: str = "t001") -> Path:
    task = Task(
        id=task_id,
        title="Old",
        type="dev",
        priority="P2",
        status="blocked",
        aspects=[],
        blocked_by=["old-string"],
        created=date(2026, 5, 1),
        description="Body.",
    )
    path = tmp_path / "tasks" / "active" / f"{task_id}-old.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(task_module.render_task_file(task), encoding="utf-8")
    return path


def _setup(tmp_path):
    seed_project(tmp_path)
    _write_dp(tmp_path, "foo")
    _write_dp(tmp_path, "bar")
    runner = CliRunner()
    runner.invoke(
        main,
        ["tasks", "add", "Block-me", "--priority", "P2"],
    )
    return runner


def _setup_host_with_peer_task(tmp_path: Path) -> Path:
    host = tmp_path / "host"
    peer = tmp_path / "peer"
    host.mkdir()
    peer.mkdir()
    (host / "science.yaml").write_text(
        f"name: host\nid: host\npeers:\n  - id: peer\n    path: {peer}\n",
        encoding="utf-8",
    )
    (peer / "science.yaml").write_text("name: peer\nid: peer\n", encoding="utf-8")
    (peer / "tasks" / "done").mkdir(parents=True)
    (peer / "tasks" / "done" / "2026-06.md").write_text(
        "## [t001] Peer task\n"
        "- type: dev\n"
        "- priority: P2\n"
        "- status: done\n"
        "- aspects: []\n"
        "- created: 2026-06-01\n"
        "- completed: 2026-06-02\n\n"
        "Done in the peer project.\n",
        encoding="utf-8",
    )
    return host


def test_tasks_block_accepts_declared_peer_task(tmp_path, monkeypatch):
    host = _setup_host_with_peer_task(tmp_path)
    _write_active_task(
        host,
        task_id="t001",
        title="Host task",
        priority="P2",
        task_type="dev",
        created=date(2026, 6, 3),
        description="Can be blocked on the peer project.",
    )

    monkeypatch.chdir(host)
    result = CliRunner().invoke(main, ["tasks", "block", "t001", "--by", "peer:task:t001"])

    assert result.exit_code == 0, result.output
    assert "peer:task:t001" in result.output
    assert task_module.parse_task_file(_active_task_path(host, "t001")).blocked_by == ["peer:task:t001"]


def test_tasks_block_rejects_untyped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    result = runner.invoke(main, ["tasks", "block", "t001", "--by", "untyped"])
    assert result.exit_code != 0
    assert "must be typed" in result.output


def test_tasks_block_repeatable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    result = runner.invoke(
        main,
        ["tasks", "block", "t001", "--by", "dataset:foo", "--by", "dataset:bar"],
    )
    assert result.exit_code == 0, result.output
    assert "dataset:foo" in result.output
    assert "dataset:bar" in result.output


def test_tasks_block_force_accepts_unknown(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    result = runner.invoke(
        main,
        ["tasks", "block", "t001", "--by", "dataset:not-yet", "--force"],
    )
    assert result.exit_code == 0, result.output
    assert "dataset:not-yet" in result.output
    assert "WARNING" in result.output


def test_tasks_blockers_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:foo"])
    result = runner.invoke(main, ["tasks", "blockers", "t001"])
    assert result.exit_code == 0, result.output
    assert "dataset:foo" in result.output
    assert "available" in result.output  # the readiness state for verified public datasets


def test_tasks_blockers_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:foo"])
    result = runner.invoke(main, ["tasks", "blockers", "t001", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["task_id"] == "t001"
    assert len(payload["blockers"]) == 1
    blocker = payload["blockers"][0]
    assert blocker["ref"] == "dataset:foo"
    assert blocker["ready"] is True
    assert blocker["state"] == "available"
    assert "detail" in blocker
    assert blocker["unresolved"] is False


def test_tasks_blockers_json_unresolved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:gone", "--force"])
    result = runner.invoke(main, ["tasks", "blockers", "t001", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    blocker = payload["blockers"][0]
    assert blocker["ref"] == "dataset:gone"
    assert blocker["unresolved"] is True
    assert blocker["ready"] is False


def test_tasks_blockers_json_resolves_declared_peer_task(tmp_path, monkeypatch):
    host = _setup_host_with_peer_task(tmp_path)
    _write_active_task(
        host,
        task_id="t001",
        title="Host task",
        priority="P2",
        status="blocked",
        task_type="dev",
        blocked_by=["peer:task:t001"],
        created=date(2026, 6, 3),
        description="Blocked on the peer project.",
    )

    monkeypatch.chdir(host)
    result = CliRunner().invoke(main, ["tasks", "blockers", "t001", "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    blocker = payload["blockers"][0]
    assert blocker["ref"] == "peer:task:t001"
    assert blocker["ready"] is True
    assert blocker["state"] == "done"
    assert blocker["unresolved"] is False


def test_tasks_edit_clear_blockers_drops_blocked_by(tmp_path, monkeypatch):
    """`tasks edit --clear-blockers` removes a stale blocked-by in-CLI (fb-2026-06-10-003)."""
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    block = runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:foo"])
    assert block.exit_code == 0, block.output
    assert task_module.parse_task_file(_active_task_path(tmp_path, "t001")).blocked_by == ["dataset:foo"]

    result = runner.invoke(main, ["tasks", "edit", "t001", "--clear-blockers"])
    assert result.exit_code == 0, result.output
    assert task_module.parse_task_file(_active_task_path(tmp_path, "t001")).blocked_by == []


def test_tasks_edit_clear_blockers_conflicts_with_blocked_by(tmp_path, monkeypatch):
    """--clear-blockers and --blocked-by are mutually exclusive."""
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    result = runner.invoke(
        main,
        ["tasks", "edit", "t001", "--clear-blockers", "--blocked-by", "dataset:foo"],
    )
    assert result.exit_code != 0
    assert "cannot be combined" in result.output


def test_tasks_fix_blockers_lists_legacy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_split_legacy_blocker(tmp_path)
    runner = CliRunner()
    # Non-interactive dry-run: just lists what would change.
    result = runner.invoke(main, ["tasks", "fix-blockers", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "t001" in result.output
    assert "old-string" in result.output


def test_tasks_fix_blockers_retypes_with_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_dp(tmp_path, "foo")
    active_path = _write_split_legacy_blocker(tmp_path)
    runner = CliRunner()
    # Interactive: provide replacement, then accept.
    result = runner.invoke(main, ["tasks", "fix-blockers"], input="dataset:foo\ny\n")
    assert result.exit_code == 0, result.output
    rewritten = active_path.read_text()
    assert "dataset:foo" in rewritten
    assert "old-string" not in rewritten


def test_tasks_fix_blockers_drops_with_empty_input(tmp_path, monkeypatch):
    """User dropping a blocker (empty input) is persisted, not silently discarded."""
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    active_path = _write_split_legacy_blocker(tmp_path)
    runner = CliRunner()
    # Interactive: empty input drops the blocker; then accept the write.
    result = runner.invoke(main, ["tasks", "fix-blockers"], input="\ny\n")
    assert result.exit_code == 0, result.output
    rewritten = active_path.read_text()
    assert "old-string" not in rewritten
    assert "Updated." in result.output


def test_tasks_fix_blockers_legacy_active_requires_migration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (tasks_dir / "active.md").write_text(
        "## [t001] Old\n"
        "- priority: P2\n"
        "- status: blocked\n"
        "- aspects: []\n"
        "- blocked-by: [old-string]\n"
        "- created: 2026-05-01\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(main, ["tasks", "fix-blockers", "--dry-run"])

    assert result.exit_code != 0
    assert "migrate-storage --apply" in str(result.exception)


# ---------------------------------------------------------------------------
# Task 11: tasks list — blocker summary, JSON readiness, all-ready nudge
# ---------------------------------------------------------------------------


def test_tasks_list_shows_blocker_summary(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:foo"])
    result = runner.invoke(main, ["tasks", "list"])
    assert result.exit_code == 0, result.output
    # Default render must include a blocker-count line for blocked tasks.
    assert "blocked-by: 1" in result.output
    # Since dataset:foo is verified-public → ready, the all-ready nudge fires.
    assert "all ready" in result.output
    assert "tasks unblock t001" in result.output


def test_tasks_list_shows_mixed_blocker_states(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_dp(tmp_path, "foo")
    # bar: embargoed/controlled dataset
    dp_dir = tmp_path / "data" / "bar"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:bar\n"
        "kind: dataset\n"
        "title: Bar\n"
        "status: active\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        "access: {level: controlled, verified: false, availability: embargoed}\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    runner.invoke(main, ["tasks", "add", "T", "--priority", "P2"])
    runner.invoke(
        main,
        ["tasks", "block", "t001", "--by", "dataset:foo", "--by", "dataset:bar"],
    )
    result = runner.invoke(main, ["tasks", "list"])
    assert result.exit_code == 0
    assert "blocked-by: 2" in result.output
    assert "embargoed" in result.output
    # Mixed → no all-ready nudge.
    assert "all ready" not in result.output


def test_tasks_list_json_includes_blocker_readiness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:foo"])
    result = runner.invoke(main, ["tasks", "list", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    blocked = [t for t in payload["rows"] if t["status"] == "blocked"]
    assert blocked
    assert "blocked_by_readiness" in blocked[0]
    readiness = blocked[0]["blocked_by_readiness"]
    assert readiness[0]["ref"] == "dataset:foo"
    assert readiness[0]["ready"] is True


def _write_embargoed_dp(tmp_path: Path) -> None:
    dp_dir = tmp_path / "data" / "embargoed"
    dp_dir.mkdir(parents=True, exist_ok=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:embargoed\n"
        "kind: dataset\n"
        "title: E\n"
        "status: active\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        "access:\n"
        "  level: controlled\n"
        "  verified: false\n"
        "  availability: embargoed\n"
        "  available_after: 2026-Q3\n",
        encoding="utf-8",
    )


def test_tasks_show_renders_per_blocker_readiness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_embargoed_dp(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["tasks", "add", "T", "--priority", "P2"])
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:embargoed"])
    result = runner.invoke(main, ["tasks", "show", "t001"])
    assert result.exit_code == 0, result.output
    assert "dataset:embargoed" in result.output
    assert "embargoed" in result.output
    assert "2026-Q3" in result.output


def test_tasks_show_accepts_format_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_embargoed_dp(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["tasks", "add", "T", "--priority", "P2"])
    runner.invoke(main, ["tasks", "block", "t001", "--by", "dataset:embargoed"])

    result = runner.invoke(main, ["tasks", "show", "t001", "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["id"] == "t001"
    assert payload["title"] == "T"
    assert payload["blocked_by_readiness"][0]["ref"] == "dataset:embargoed"
    assert payload["blocked_by_readiness"][0]["state"] == "embargoed"


def test_tasks_summary_accepts_format_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = _setup(tmp_path)
    runner.invoke(main, ["tasks", "add", "Second", "--priority", "P1"])

    result = runner.invoke(main, ["tasks", "summary", "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["total"] == 2
    assert payload["by_status"]["proposed"] == 2
    assert payload["by_priority"]["P2"] == 1
    assert payload["by_priority"]["P1"] == 1


def test_tasks_list_warns_about_legacy_blockers_in_split_layout(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    seed_project(tmp_path)
    _write_active_task(
        tmp_path,
        task_id="t001",
        title="Clean",
        status="active",
        blocked_by=["dataset:foo"],
    )
    _write_split_legacy_blocker(tmp_path, task_id="t002")

    result = CliRunner().invoke(main, ["tasks", "list"])

    assert result.exit_code == 0, result.output
    assert "t001" in result.output
    assert "t002" in result.output
    assert "WARNING: task t002: legacy untyped blocker 'old-string'" in result.stderr
    assert "task t001:" not in result.stderr
