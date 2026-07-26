"""Tests for `list_tasks(..., since=...)`: archive-reading completion-date filter."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from science_tool.tasks import list_tasks, parse_tasks, render_task_file, render_tasks


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _older_month(year: int, month: int, back: int) -> tuple[int, int]:
    for _ in range(back):
        year, month = _prev_month(year, month)
    return year, month


TODAY = date.today()
BOUNDARY_YEAR, BOUNDARY_MONTH = _prev_month(TODAY.year, TODAY.month)
BOUNDARY_MONTH_STR = f"{BOUNDARY_YEAR:04d}-{BOUNDARY_MONTH:02d}"
CURRENT_MONTH_STR = TODAY.strftime("%Y-%m")
SINCE = date(BOUNDARY_YEAR, BOUNDARY_MONTH, 15)

# A month with no archive file at all, further back than any fixture file --
# used to prove an absent month in the window is not an error.
NO_FILE_YEAR, NO_FILE_MONTH = _older_month(BOUNDARY_YEAR, BOUNDARY_MONTH, 2)
NO_FILE_SINCE = date(NO_FILE_YEAR, NO_FILE_MONTH, 1)

ACTIVE_MD = """\
## [t001] Still open
- type: dev
- priority: P1
- status: active
- created: 2026-01-01

Open, no completed date -- must never appear in --since results.

## [t002] Retired with completed date
- type: dev
- priority: P2
- status: retired
- created: 2026-01-01
- completed: {today}

Retired tasks participate in --since by default.

## [t003] Open status with a stray completed date
- type: dev
- priority: P1
- status: active
- created: 2026-01-01
- completed: {today}

An anomalous open task carrying a stray `completed:` date must not leak
into --since results -- the keep-predicate requires a closed status.
"""

BOUNDARY_ARCHIVE_MD = """\
## [t010] Before the cutoff
- type: dev
- priority: P1
- status: done
- created: 2026-01-01
- completed: {before}

Completed the day before `since` -- excluded.

## [t011] Exactly on the cutoff
- type: dev
- priority: P1
- status: done
- created: 2026-01-01
- completed: {since}

Completed exactly on `since` -- exact-cutoff inclusion.

## [t012] After the cutoff, same month
- type: dev
- priority: P2
- status: done
- created: 2026-01-01
- completed: {after}

Completed later in the same boundary month -- included.
"""

CURRENT_ARCHIVE_MD = """\
## [t020] Done with no completed date
- type: dev
- priority: P1
- status: done
- created: 2026-01-01

Routed to the current month by the archiver's fallback, but has no
`completed:` field -- must be excluded from --since results AND counted
in the missing-completed stderr note.
"""


def _setup(tmp_path: Path) -> Path:
    tasks_dir = tmp_path / "tasks"
    fixture_path = tmp_path / "active-fixture.md"
    _write(fixture_path, ACTIVE_MD.format(today=TODAY.isoformat()))
    fixture_tasks = parse_tasks(fixture_path)
    active_dir = tasks_dir / "active"
    for task in fixture_tasks:
        if task.status not in {"done", "retired"}:
            _write(active_dir / f"{task.id}.md", render_task_file(task))

    before = date(BOUNDARY_YEAR, BOUNDARY_MONTH, 14).isoformat()
    after = date(BOUNDARY_YEAR, BOUNDARY_MONTH, 20).isoformat()
    _write(
        tasks_dir / "done" / f"{BOUNDARY_MONTH_STR}.md",
        BOUNDARY_ARCHIVE_MD.format(before=before, since=SINCE.isoformat(), after=after),
    )
    retired = [task for task in fixture_tasks if task.status == "retired"]
    _write(
        tasks_dir / "done" / f"{CURRENT_MONTH_STR}.md",
        render_tasks(retired) + CURRENT_ARCHIVE_MD,
    )
    return tasks_dir


class TestSinceFilter:
    def test_exact_cutoff_included(self, tmp_path: Path) -> None:
        tasks_dir = _setup(tmp_path)
        result = list_tasks(tasks_dir, since=SINCE)
        ids = {t.id for t in result}
        assert "t011" in ids

    def test_boundary_month_only_on_or_after_since(self, tmp_path: Path) -> None:
        tasks_dir = _setup(tmp_path)
        result = list_tasks(tasks_dir, since=SINCE)
        ids = {t.id for t in result}
        assert "t010" not in ids
        assert {"t011", "t012"} <= ids

    def test_missing_completed_excluded_and_counted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        tasks_dir = _setup(tmp_path)
        result = list_tasks(tasks_dir, since=SINCE)
        ids = {t.id for t in result}
        assert "t020" not in ids
        captured = capsys.readouterr()
        assert "1" in captured.err
        assert "completed" in captured.err.lower()

    def test_retired_included_by_default_and_status_narrows(self, tmp_path: Path) -> None:
        tasks_dir = _setup(tmp_path)
        result = list_tasks(tasks_dir, since=SINCE)
        ids = {t.id for t in result}
        assert "t002" in ids

        narrowed = list_tasks(tasks_dir, since=SINCE, status="done")
        narrowed_ids = {t.id for t in narrowed}
        assert "t002" not in narrowed_ids
        assert "t011" in narrowed_ids

    def test_open_task_never_appears(self, tmp_path: Path) -> None:
        tasks_dir = _setup(tmp_path)
        result = list_tasks(tasks_dir, since=SINCE)
        ids = {t.id for t in result}
        assert "t001" not in ids

    def test_open_status_with_stray_completed_date_excluded(self, tmp_path: Path) -> None:
        tasks_dir = _setup(tmp_path)
        result = list_tasks(tasks_dir, since=SINCE)
        ids = {t.id for t in result}
        # t003 is status "active" (open) but carries a completed: date on or
        # after `since` -- the keep-predicate must require a closed status,
        # not just a qualifying completed date.
        assert "t003" not in ids

    def test_window_month_with_no_archive_file_is_not_an_error(self, tmp_path: Path) -> None:
        tasks_dir = _setup(tmp_path)
        # NO_FILE_SINCE's month window includes NO_FILE_YEAR/MONTH (and the
        # month after it), neither of which has a done/*.md file on disk --
        # must not raise, and existing fixture data (all completed after
        # NO_FILE_SINCE) should still surface normally.
        result = list_tasks(tasks_dir, since=NO_FILE_SINCE)
        ids = {t.id for t in result}
        assert {"t010", "t011", "t012", "t002"} <= ids

    def test_since_none_is_unchanged_default_behavior(self, tmp_path: Path) -> None:
        tasks_dir = _setup(tmp_path)
        result = list_tasks(tasks_dir)
        ids = {t.id for t in result}
        # Default listing hides done/retired and never reads archives.
        assert ids == {"t001", "t003"}
