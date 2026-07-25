"""Actual emitted sizes for every wired command, in every supported format.

The boundary guards prove classification and wiring; this proves size.
"""

from __future__ import annotations

import json
import re
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
TASK_IDS = {f"t{i:03d}" for i in range(400)}
DATA_RECORD_PATHS = {
    f"data/stranded-record-with-a-long-name-{i:05d}.md" for i in range(3_000)
}


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


def _task_ids(text: str) -> set[str]:
    return set(re.findall(r"\bt\d{3}\b", text))


def _data_record_paths(text: str) -> set[str]:
    return set(re.findall(r"data/stranded-record-with-a-long-name-\d{5}\.md", text))


def test_tasks_json_output_file_is_complete(project: Path) -> None:
    target = project / "tasks.json"
    result = _invoke(["tasks", "list", "--all", "--format", "json", "--output", str(target)])
    assert result.exit_code == 0, result.output

    payload = json.loads(target.read_text())
    assert {row["id"] for row in payload["rows"]} == TASK_IDS
    assert len(payload["rows"]) == 400
    assert payload["meta"]["returned_count"] == 400
    assert payload["meta"]["active_total"] == 400
    assert "truncation" not in payload


def test_tasks_table_output_file_is_complete(project: Path) -> None:
    target = project / "tasks.txt"
    result = _invoke(["tasks", "list", "--all", "--output", str(target)])
    assert result.exit_code == 0, result.output

    written = target.read_text()
    assert _task_ids(written) == TASK_IDS
    assert "showing " not in written
    assert "complete output:" not in written


def test_health_json_output_file_is_complete_and_unprojected(project: Path) -> None:
    target = project / "health.json"
    result = _invoke(["health", "--format", "json", "--output", str(target)])
    assert result.exit_code == 0, result.output

    written = target.read_text()
    payload = json.loads(written)
    assert _task_ids(written) == TASK_IDS
    assert len(payload["validation"]) > 40
    assert payload["total_issues"] > 40
    assert "section_omitted" not in payload
    assert "displayed_issues" not in payload


def test_health_table_output_file_is_complete_and_unprojected(project: Path) -> None:
    target = project / "health.txt"
    result = _invoke(["health", "--output", str(target)])
    assert result.exit_code == 0, result.output

    written = target.read_text()
    assert _task_ids(written) == TASK_IDS
    assert "finding(s) hidden" not in written
    assert "showing " not in written


def test_inventory_output_file_contains_every_entity(project: Path) -> None:
    target = project / "inventory.json"
    result = _invoke(
        [
            "entities",
            "inventory",
            "--project-root",
            str(project),
            "--output",
            str(target),
        ]
    )
    assert result.exit_code == 0, result.output

    payload = json.loads(target.read_text())
    assert payload["schema_version"] == "2"
    assert len(payload["entities"]) == 701
    assert sum(entity["kind"] == "question" for entity in payload["entities"]) == 300
    assert sum(entity["kind"] == "task" for entity in payload["entities"]) == 400
    assert sum(entity["kind"] == "hypothesis" for entity in payload["entities"]) == 1


def test_data_audit_text_output_file_contains_every_record(project: Path) -> None:
    target = project / "audit.txt"
    result = _invoke(["data", "audit", "--output", str(target)])
    assert result.exit_code == 1, result.output

    written = target.read_text()
    assert _data_record_paths(written) == DATA_RECORD_PATHS
    assert written.count("data/stranded-record-with-a-long-name-") == 3_000


def test_data_audit_json_output_file_contains_every_record(project: Path) -> None:
    target = project / "audit.json"
    result = _invoke(["data", "audit", "--format", "json", "--output", str(target)])
    assert result.exit_code == 1, result.output

    payload = json.loads(target.read_text())
    data_paths = [
        row["path"]
        for row in payload["violations"]
        if row["path"].startswith("data/stranded-record-with-a-long-name-")
    ]
    assert payload["version"] == 1
    assert len(data_paths) == 3_000
    assert set(data_paths) == DATA_RECORD_PATHS


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
