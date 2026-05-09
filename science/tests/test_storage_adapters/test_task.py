"""Tests for TaskAdapter — wraps the existing task DSL parser."""

from __future__ import annotations

from pathlib import Path

import pytest

import science_tool.graph.storage_adapters.task as task_module
from science_tool.graph.storage_adapters.task import TaskAdapter


def test_adapter_name() -> None:
    assert TaskAdapter().name == "task"


def test_discovers_tasks_under_tasks_dir(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n\nBody.\n",
        encoding="utf-8",
    )
    refs = TaskAdapter().discover(tmp_path)
    assert len(refs) == 1
    assert refs[0].adapter_name == "task"


def test_load_raw_produces_task_entity_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n\nBody prose.\n",
        encoding="utf-8",
    )
    a = TaskAdapter()
    refs = a.discover(tmp_path)
    monkeypatch.chdir(tmp_path)
    raw = a.load_raw(refs[0])
    assert raw["kind"] == "task"
    assert raw["canonical_id"] == "task:t001"
    assert raw["title"] == "T01"
    assert raw["priority"] == "P1"
    assert raw["status"] == "active"
    assert raw["content"].strip().startswith("Body prose")


def test_returns_empty_when_no_tasks_dir(tmp_path: Path) -> None:
    assert TaskAdapter().discover(tmp_path) == []


def test_multiple_tasks_in_one_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n\n"
        "## [t002] T02\n- type: research\n- priority: P2\n- status: active\n- created: 2026-04-20\n\n",
        encoding="utf-8",
    )
    refs = TaskAdapter().discover(tmp_path)
    assert len(refs) == 2
    assert refs[0].line == 0
    assert refs[1].line == 1
    monkeypatch.chdir(tmp_path)
    raws = [TaskAdapter().load_raw(r) for r in refs]
    ids = {r["canonical_id"] for r in raws}
    assert ids == {"task:t001", "task:t002"}


def test_discover_ignores_historical_alias_archive(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n\n",
        encoding="utf-8",
    )
    (tmp_path / "tasks" / "archive.md").write_text(
        "# Historical task aliases\n\n"
        "## [t024] Old analysis task\n"
        "- status: archived\n"
        "- note: Kept only so older documents can resolve task:t024.\n\n"
        "## [t35] Legacy short-form task\n"
        "- status: archived\n"
        "- note: Short-form historical alias.\n",
        encoding="utf-8",
    )

    refs = TaskAdapter().discover(tmp_path)

    assert len(refs) == 1


def test_load_raw_uses_discovered_tasks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] T01\n- type: research\n- priority: P1\n- status: active\n- created: 2026-04-20\n\n"
        "## [t002] T02\n- type: research\n- priority: P2\n- status: active\n- created: 2026-04-20\n\n",
        encoding="utf-8",
    )
    adapter = TaskAdapter()
    refs = adapter.discover(tmp_path)

    def fail_reparse(_path: Path) -> list[object]:
        raise AssertionError("load_raw reparsed task markdown")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(task_module, "parse_tasks", fail_reparse)

    assert [adapter.load_raw(ref)["canonical_id"] for ref in refs] == ["task:t001", "task:t002"]


def test_load_raw_includes_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t016] Follow-up\n"
        "- type: research\n"
        "- priority: P1\n"
        "- status: active\n"
        "- parent: task:t001\n"
        "- created: 2026-05-05\n\n"
        "Body prose.\n",
        encoding="utf-8",
    )
    adapter = TaskAdapter()
    refs = adapter.discover(tmp_path)
    monkeypatch.chdir(tmp_path)

    raw = adapter.load_raw(refs[0])

    assert raw["parent"] == "task:t001"
