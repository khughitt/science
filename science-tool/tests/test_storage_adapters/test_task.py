"""Tests for TaskAdapter — wraps the existing task DSL parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.storage_adapters.task import TaskAdapter


def test_adapter_name() -> None:
    assert TaskAdapter().name == "task"


def test_discovers_tasks_under_tasks_dir(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t01] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n\nBody.\n",
        encoding="utf-8",
    )
    refs = TaskAdapter().discover(tmp_path)
    assert len(refs) == 1
    assert refs[0].adapter_name == "task"


def test_load_raw_produces_task_entity_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t01] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n\nBody prose.\n",
        encoding="utf-8",
    )
    a = TaskAdapter()
    refs = a.discover(tmp_path)
    monkeypatch.chdir(tmp_path)
    raw = a.load_raw(refs[0])
    assert raw["kind"] == "task"
    assert raw["canonical_id"] == "task:t01"
    assert raw["title"] == "T01"
    assert raw["priority"] == "P1"
    assert raw["status"] == "active"
    assert raw["content"].strip().startswith("Body prose")


def test_returns_empty_when_no_tasks_dir(tmp_path: Path) -> None:
    assert TaskAdapter().discover(tmp_path) == []


def test_multiple_tasks_in_one_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t01] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n\n"
        "## [t02] T02\n- type: research\n- priority: P2\n- status: active\n- created: 2026-04-20\n\n",
        encoding="utf-8",
    )
    refs = TaskAdapter().discover(tmp_path)
    assert len(refs) == 2
    assert refs[0].line == 0
    assert refs[1].line == 1
    monkeypatch.chdir(tmp_path)
    raws = [TaskAdapter().load_raw(r) for r in refs]
    ids = {r["canonical_id"] for r in raws}
    assert ids == {"task:t01", "task:t02"}
