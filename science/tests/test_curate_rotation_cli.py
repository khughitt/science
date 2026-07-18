"""CLI tests for `entity rotation`."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from _fixtures.entity_helpers import write_markdown_entity

from science_tool.cli import main as cli_main


def _make_project(tmp_path: Path, count: int) -> Path:
    root = tmp_path / "proj"
    (root / "entities").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n", encoding="utf-8")
    for i in range(1, count + 1):
        write_markdown_entity(
            root,
            f"entities/plans/{i:04d}.md",
            {
                "id": f"plan:{i:04d}",
                "kind": "plan",
                "title": "P",
                "status": "active",
                "review_state": {"last_reviewed": f"2026-05-{i:02d}"},
            },
        )
    return root


def test_rotation_json_shape(tmp_path: Path, monkeypatch) -> None:
    root = _make_project(tmp_path, 3)
    monkeypatch.chdir(root)
    result = CliRunner().invoke(cli_main, ["entity", "rotation", "--format", "json"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["format"] == "json"
    assert payload["meta"] == {
        "pool_size": 3,
        "budget": 3,
        "displayed": 3,
        "coverage_rounds": 1,
        "graph_source": "absent",
    }
    rows = payload["rows"]
    assert [row["id"] for row in rows] == ["plan:0001", "plan:0002", "plan:0003"]
    assert set(rows[0]) == {"id", "last_reviewed", "age_days", "rank", "selected", "freshness"}
    assert rows[0]["selected"] is True
    assert rows[0]["freshness"] is None


def test_rotation_all_shows_full_queue_but_budgets_prefix(tmp_path: Path, monkeypatch) -> None:
    root = _make_project(tmp_path, 30)  # N=30 > N_FULL -> budget < 30
    monkeypatch.chdir(root)
    result = CliRunner().invoke(cli_main, ["entity", "rotation", "--all", "--format", "json"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["meta"]["pool_size"] == 30
    assert payload["meta"]["budget"] < 30
    assert payload["meta"]["displayed"] == 30  # --all shows every row
    rows = payload["rows"]
    assert len(rows) == 30
    selected = [row for row in rows if row["selected"]]
    assert len(selected) == payload["meta"]["budget"]  # only the prefix is selected


def test_rotation_default_displays_only_budget(tmp_path: Path, monkeypatch) -> None:
    root = _make_project(tmp_path, 30)
    monkeypatch.chdir(root)
    result = CliRunner().invoke(cli_main, ["entity", "rotation", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["rows"]) == payload["meta"]["budget"]
    assert payload["meta"]["displayed"] == payload["meta"]["budget"]


def test_rotation_table_renders_never(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "proj"
    (root / "entities").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n", encoding="utf-8")
    write_markdown_entity(
        root, "entities/plans/0001.md", {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active"}
    )
    monkeypatch.chdir(root)
    result = CliRunner().invoke(cli_main, ["entity", "rotation"])
    assert result.exit_code == 0, result.output
    assert "never" in result.output
    assert "1 of 1" in result.output  # dynamic title carries budget/pool
    assert "coverage:" in result.output  # nonempty output carries the coverage clause


def test_rotation_empty_corpus_table_omits_coverage_clause(tmp_path: Path, monkeypatch) -> None:
    """Table output only: the coverage clause is omitted when coverage_rounds == 0.

    (JSON never renders a title, so clause omission can only be asserted on the table.)
    """
    root = tmp_path / "proj"
    (root / "entities").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n", encoding="utf-8")
    write_markdown_entity(
        root, "entities/datasets/d1.md", {"id": "dataset:d1", "kind": "dataset", "title": "D", "status": "active"}
    )
    monkeypatch.chdir(root)
    result = CliRunner().invoke(cli_main, ["entity", "rotation"])  # table
    assert result.exit_code == 0, result.output
    assert "0 of 0" in result.output  # dynamic title still carries budget/pool
    assert "coverage:" not in result.output  # clause omitted when coverage_rounds == 0
