"""Actual emitted sizes for every wired command, in every supported format.

The boundary guards prove classification and wiring; this proves size.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.budget.measure import visible_len
from science_tool.budget.registry import BUDGETS
from science_tool.cli import main

TASKS = "\n".join(
    f"""## [t{i:03d}] Task {i} with a deliberately long title to exercise wrapping behaviour
- priority: P2
- status: {"active" if i < 5 else "proposed"}
- related: [question:q0000-a-long-question-slug, hypothesis:h0000-another-long-slug]
- created: 2026-01-01

Body paragraph for task {i}, long enough to matter multiplied by the backlog size.
"""
    for i in range(400)
)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "active.md").write_text(TASKS)
    entities = tmp_path / "entities" / "questions"
    entities.mkdir(parents=True)
    for i in range(300):
        entity_id = "question:q0000-a-long-question-slug" if i == 0 else f"question:q{i:04d}"
        (entities / f"{i:04d}-q.md").write_text(
            f"---\nid: {entity_id}\nkind: question\ntitle: Question {i}\n---\n\n" + ("body " * 300)
        )
    hypotheses = tmp_path / "entities" / "hypotheses"
    hypotheses.mkdir()
    (hypotheses / "0000-h.md").write_text(
        "---\nid: hypothesis:h0000-another-long-slug\nkind: hypothesis\n"
        "title: Referenced hypothesis\n---\n\n"
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    for i in range(3_000):
        (data_dir / f"stranded-record-with-a-long-name-{i:05d}.md").write_text("x")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def _scope_project(args: list[str], project: Path) -> list[str]:
    """Make inventory tests independent of its import-time Path.cwd() default."""
    if args[:2] == ["entities", "inventory"]:
        return [*args, "--project-root", str(project)]
    return args


@pytest.mark.parametrize(
    ("command_path", "args"),
    [
        ("tasks list", ["tasks", "list"]),
        ("tasks list", ["tasks", "list", "--status", "proposed"]),
        ("tasks list", ["tasks", "list", "--status", "proposed", "--format", "json"]),
        ("health", ["health"]),
        ("health", ["health", "--format", "json"]),
        ("health", ["health", "--severity", "all"]),
    ],
)
def test_command_stays_within_its_ceiling(project: Path, command_path: str, args: list[str]) -> None:
    result = _invoke(args)
    assert result.exit_code == 0, result.output
    ceiling = BUDGETS[command_path].max_chars
    assert visible_len(result.output) <= ceiling, f"{args} emitted {visible_len(result.output)} > {ceiling}"


@pytest.mark.parametrize(
    ("command_path", "args"),
    [
        ("entities inventory", ["entities", "inventory"]),
        ("data audit", ["data", "audit"]),
        ("data audit", ["data", "audit", "--format", "json"]),
    ],
)
def test_bulk_dump_refuses_rather_than_flooding(project: Path, command_path: str, args: list[str]) -> None:
    """DOCUMENT-shaped commands refuse; they never emit a partial payload."""
    result = _invoke(_scope_project(args, project))
    assert result.exit_code != 0
    assert "--output" in result.output
    assert visible_len(result.output) <= BUDGETS[command_path].max_chars


@pytest.mark.parametrize(
    ("args", "target_name"),
    [
        (["tasks", "list", "--status", "proposed", "--format", "json"], "tasks.json"),
        (["tasks", "list", "--status", "proposed"], "tasks.txt"),
        (["health", "--format", "json"], "health.json"),
        (["health"], "health.txt"),
        (["entities", "inventory"], "inventory.json"),
        (["data", "audit"], "audit.txt"),
        (["data", "audit", "--format", "json"], "audit.json"),
    ],
)
def test_output_file_is_written_and_non_empty(project: Path, args: list[str], target_name: str) -> None:
    target = project / target_name
    result = _invoke([*_scope_project(args, project), "--output", str(target)])
    assert result.exit_code in (0, 1), result.output
    assert target.is_file(), f"{args} --output wrote no file"
    assert target.stat().st_size > 0, f"{args} --output wrote an empty file"


@pytest.mark.parametrize(
    ("args", "target_name"),
    [
        (["tasks", "list", "--status", "proposed", "--format", "json"], "tasks.json"),
        (["tasks", "list", "--status", "proposed"], "tasks.txt"),
        (["health", "--format", "json"], "health.json"),
        (["health"], "health.txt"),
        (["entities", "inventory"], "inventory.json"),
        (["data", "audit"], "audit.txt"),
        (["data", "audit", "--format", "json"], "audit.json"),
    ],
)
def test_no_success_message_when_the_command_fails(
    project: Path, args: list[str], target_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sole payload-sink bypass must follow a successful flush, not sit in `finally`."""
    from science_tool.budget import sink as sink_module

    def _boom(self: object) -> None:
        raise RuntimeError("render failed")

    monkeypatch.setattr(sink_module.BoundedSink, "flush", _boom)
    result = _invoke([*_scope_project(args, project), "--output", str(project / target_name)])
    assert result.exit_code != 0
    assert "wrote" not in result.output


def test_tasks_list_json_reports_the_full_total(project: Path) -> None:
    result = _invoke(["tasks", "list", "--status", "proposed", "--format", "json"])
    assert json.loads(result.output)["truncation"]["total"] == 395
