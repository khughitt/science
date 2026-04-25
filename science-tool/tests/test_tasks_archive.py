"""Tests for the tasks_archive module."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.tasks_archive import (
    ArchiveEntry,
    ArchivePlan,
    ParseError,
    plan_archive,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


PROPOSED_BLOCK = """\
## [t001] Proposed task
- priority: P1
- status: proposed
- created: 2026-04-01

Description.
"""

DONE_MARCH = """\
## [t002] Done in March
- priority: P1
- status: done
- created: 2026-03-01
- completed: 2026-03-15

Done description.
"""

DONE_NO_COMPLETED = """\
## [t003] Done with no completed date
- priority: P2
- status: done
- created: 2026-03-01

Missing completed.
"""

RETIRED_APRIL = """\
## [t004] Retired in April
- priority: P3
- status: retired
- created: 2026-03-20
- completed: 2026-04-02

Retired description.
"""

DEFERRED_BLOCK = """\
## [t005] Deferred task
- priority: P2
- status: deferred
- created: 2026-04-01

Deferred description.
"""

BLOCKED_BLOCK = """\
## [t006] Blocked task
- priority: P1
- status: blocked
- created: 2026-04-01

Blocked description.
"""


# ---------------------------------------------------------------------------
# Planner tests
# ---------------------------------------------------------------------------


class TestPlanner:
    def test_planner_empty_active_returns_empty_plan(self, tmp_path: Path) -> None:
        plan = plan_archive(tmp_path, today=date(2026, 4, 25))
        assert plan.entries == []
        assert plan.parse_errors == []
        assert plan.remaining == []
        assert plan.preamble == ""

    def test_planner_missing_active_md_returns_empty_plan(self, tmp_path: Path) -> None:
        plan = plan_archive(tmp_path, today=date(2026, 4, 25))
        assert plan.entries == []
        assert plan.remaining == []

    def test_planner_done_routes_to_completed_month(self, tmp_path: Path) -> None:
        _write(tmp_path / "active.md", DONE_MARCH)
        plan = plan_archive(tmp_path, today=date(2026, 4, 25))
        assert len(plan.entries) == 1
        entry = plan.entries[0]
        assert entry.task.id == "t002"
        assert entry.destination == tmp_path / "done" / "2026-03.md"
        assert entry.missing_completed is False
        assert plan.remaining == []

    def test_planner_retired_routes_to_completed_month(self, tmp_path: Path) -> None:
        _write(tmp_path / "active.md", RETIRED_APRIL)
        plan = plan_archive(tmp_path, today=date(2026, 4, 25))
        assert len(plan.entries) == 1
        entry = plan.entries[0]
        assert entry.task.id == "t004"
        assert entry.destination == tmp_path / "done" / "2026-04.md"
        assert entry.missing_completed is False

    def test_planner_done_without_completed_falls_back_to_today(self, tmp_path: Path) -> None:
        _write(tmp_path / "active.md", DONE_NO_COMPLETED)
        plan = plan_archive(tmp_path, today=date(2026, 4, 25))
        assert len(plan.entries) == 1
        entry = plan.entries[0]
        assert entry.task.id == "t003"
        assert entry.destination == tmp_path / "done" / "2026-04.md"
        assert entry.missing_completed is True

    def test_planner_deferred_stays_in_active(self, tmp_path: Path) -> None:
        _write(tmp_path / "active.md", DEFERRED_BLOCK)
        plan = plan_archive(tmp_path, today=date(2026, 4, 25))
        assert plan.entries == []
        assert len(plan.remaining) == 1
        assert plan.remaining[0].id == "t005"

    def test_planner_mixed_only_terminal_archived(self, tmp_path: Path) -> None:
        content = "\n".join([PROPOSED_BLOCK, DONE_MARCH, RETIRED_APRIL, BLOCKED_BLOCK])
        _write(tmp_path / "active.md", content)
        plan = plan_archive(tmp_path, today=date(2026, 4, 25))
        archived_ids = {e.task.id for e in plan.entries}
        remaining_ids = {t.id for t in plan.remaining}
        assert archived_ids == {"t002", "t004"}
        assert remaining_ids == {"t001", "t006"}

    def test_planner_preserves_preamble_byte_for_byte(self, tmp_path: Path) -> None:
        preamble = "# Active Tasks\n\nNote.\n\n"
        _write(tmp_path / "active.md", preamble + DONE_MARCH)
        plan = plan_archive(tmp_path, today=date(2026, 4, 25))
        assert plan.preamble == preamble
        assert len(plan.entries) == 1

    def test_planner_no_preamble_yields_empty_string(self, tmp_path: Path) -> None:
        _write(tmp_path / "active.md", DONE_MARCH)
        plan = plan_archive(tmp_path, today=date(2026, 4, 25))
        assert plan.preamble == ""

    def test_planner_records_parse_error_and_continues(self, tmp_path: Path) -> None:
        bad_block = "## [t099] Bad task\n- priority: P1\n- status: done\n\nBody.\n"
        content = "\n".join([bad_block, DONE_MARCH])
        _write(tmp_path / "active.md", content)
        plan = plan_archive(tmp_path, today=date(2026, 4, 25))
        assert len(plan.parse_errors) == 1
        assert "t099" in plan.parse_errors[0].heading
        assert len(plan.entries) == 1
        assert plan.entries[0].task.id == "t002"


def test_archive_dataclass_fields() -> None:
    from science_tool.tasks import Task

    task = Task(
        id="t001",
        title="x",
        priority="P1",
        status="done",
        created=date(2026, 4, 1),
        completed=date(2026, 4, 2),
    )
    entry = ArchiveEntry(task=task, destination=Path("/tmp/done/2026-04.md"), missing_completed=False)
    assert entry.task.id == "t001"
    plan = ArchivePlan(
        tasks_dir=Path("/tmp"),
        preamble="",
        entries=[entry],
        parse_errors=[],
        remaining=[],
    )
    assert plan.entries[0] is entry
    err = ParseError(heading="## [t099] x", message="bad")
    assert err.heading.startswith("##")
