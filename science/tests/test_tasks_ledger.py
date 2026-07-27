from datetime import date
from pathlib import Path

import pytest
from science_model.tasks import Task
from science_tool.tasks_ledger import _destination_for, _read_destination


def test_destination_uses_completed_month():
    t = Task(id="t005", title="x", status="done", created=date(2026, 3, 1),
             completed=date(2026, 3, 15))
    dest, missing = _destination_for(t, date(2026, 4, 25))
    assert dest == Path("done") / "2026-03.md"
    assert missing is False


def test_destination_falls_back_to_today_when_undated():
    t = Task(id="t006", title="x", status="retired", created=date(2026, 3, 1))
    dest, missing = _destination_for(t, date(2026, 4, 25))
    assert dest == Path("done") / "2026-04.md"
    assert missing is True


def test_read_destination_missing_file(tmp_path: Path):
    assert _read_destination(tmp_path / "done" / "2026-01.md") == ("", [])


def test_read_destination_rejects_noncanonical_task_like_heading(tmp_path: Path):
    path = tmp_path / "done" / "2026-01.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "# Existing ledger\n\n"
        "## [t01] Noncanonical task\n"
        "- priority: P1\n"
        "- status: done\n"
        "- aspects: []\n"
        "- created: 2026-01-01\n\n"
        "Do not erase this block.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"Invalid task id 't01'"):
        _read_destination(path)
