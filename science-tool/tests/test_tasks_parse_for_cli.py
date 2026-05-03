"""Tests for the CLI-only parse wrapper that surfaces legacy-blocker warnings."""
from __future__ import annotations

from pathlib import Path

from science_tool.tasks import parse_tasks, parse_tasks_for_cli


def _write_active(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "active.md"
    path.write_text(body, encoding="utf-8")
    return path


_LEGACY_TASK = """## [t001] Old task
- type: dev
- priority: P2
- status: blocked
- blocked-by: [some-old-string, dataset:foo]
- created: 2026-05-01

Body.
"""


def test_parse_tasks_does_not_emit_warnings(tmp_path: Path):
    path = _write_active(tmp_path, _LEGACY_TASK)
    tasks = parse_tasks(path)
    assert len(tasks) == 1
    assert tasks[0].blocked_by == ["some-old-string", "dataset:foo"]


def test_parse_tasks_for_cli_warns_about_untyped_blockers(tmp_path: Path):
    path = _write_active(tmp_path, _LEGACY_TASK)
    tasks, warnings = parse_tasks_for_cli(path)
    assert len(tasks) == 1
    assert any("some-old-string" in w for w in warnings)
    # Properly typed refs do NOT generate warnings.
    assert not any("dataset:foo" in w for w in warnings)


def test_parse_tasks_for_cli_no_warnings_when_all_typed(tmp_path: Path):
    body = """## [t001] All-typed
- type: dev
- priority: P2
- status: blocked
- blocked-by: [dataset:foo, task:t002]
- created: 2026-05-01

Body.
"""
    path = _write_active(tmp_path, body)
    tasks, warnings = parse_tasks_for_cli(path)
    assert len(tasks) == 1
    assert warnings == []
