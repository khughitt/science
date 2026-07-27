from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from click.testing import CliRunner
from science_model.tasks import Task

from science_tool.budget.measure import visible_len
from science_tool.budget.registry import BUDGETS
from science_tool.cli import main
from science_tool.tasks import render_task_file


def _project(root: Path) -> None:
    (root / "science.yaml").write_text("id: demo\nname: demo\n")
    active_dir = root / "tasks" / "active"
    active_dir.mkdir(parents=True, exist_ok=True)
    for i in range(200):
        task = Task(
            id=f"t{i:03d}",
            title=f"Task {i} with a deliberately long title to exercise wrapping",
            priority="P2",
            status="active" if i < 3 else "proposed",
            related=[
                f"question:q{i:04d}-a-long-question-slug",
                f"hypothesis:h{i:04d}-another-long-slug",
            ],
            created=date(2026, 1, 1),
            description=f"Body for task {i}.",
        )
        (active_dir / f"{task.id}-task-{i}.md").write_text(
            render_task_file(task),
            encoding="utf-8",
        )


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def test_default_list_shows_only_the_working_set() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        _project(Path(fs))
        result = _invoke(["tasks", "list", "--format", "json"])
        assert result.exit_code == 0, result.output
        assert {row["status"] for row in json.loads(result.output)["rows"]} == {"active"}


def test_table_branch_is_projected_and_stays_within_budget() -> None:
    """The regression the previous plan missed: table output must project, not raise."""
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        _project(Path(fs))
        result = _invoke(["tasks", "list", "--status", "proposed"])
        assert result.exit_code == 0, result.output
        assert visible_len(result.output) <= BUDGETS["tasks list"].max_chars
        assert "of 197 rows" in result.output


def test_table_footer_escape_preserves_the_user_selection() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        _project(Path(fs))
        result = _invoke(["tasks", "list", "--status", "proposed"])
        assert "--status proposed" in result.output
        assert "--output" in result.output


def test_json_branch_stays_within_budget() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        _project(Path(fs))
        result = _invoke(["tasks", "list", "--status", "proposed", "--format", "json"])
        assert result.exit_code == 0, result.output
        assert visible_len(result.output) <= BUDGETS["tasks list"].max_chars
        assert json.loads(result.output)["truncation"]["total"] == 197


def test_output_file_is_complete_in_json() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        root = Path(fs)
        _project(root)
        target = root / "tasks.json"
        result = _invoke(
            ["tasks", "list", "--status", "proposed", "--format", "json", "--output", str(target)]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(target.read_text())
        assert len(payload["rows"]) == 197
        assert "truncation" not in payload


def test_output_file_is_complete_in_table_format() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as fs:
        root = Path(fs)
        _project(root)
        target = root / "tasks.txt"
        result = _invoke(["tasks", "list", "--status", "proposed", "--output", str(target)])
        assert result.exit_code == 0, result.output
        written = target.read_text()
        assert "t199" in written
        assert "of 197 rows" not in written  # complete, so no truncation footer
        assert str(target) in result.output
