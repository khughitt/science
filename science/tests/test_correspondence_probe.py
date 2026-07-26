from pathlib import Path

import pytest

from science_tool.correspondence.probe import (
    ProbeResult,
    TaskState,
    probe_path,
    resolve_task,
)


def _write_active_task(root: Path, task_id: str) -> None:
    path = root / "tasks" / "active" / f"{task_id}-thing.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"id: {task_id}\n"
        "title: Thing\n"
        "priority: P1\n"
        "status: active\n"
        "aspects: []\n"
        "created: 2026-07-01\n"
        "---\n\n"
        "Body.\n"
    )


def _write_done_task(root: Path, task_id: str) -> None:
    path = root / "tasks" / "done" / "2026-07.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"## [{task_id}] Thing\n"
        "- priority: P1\n"
        "- status: done\n"
        "- aspects: []\n"
        "- created: 2026-07-01\n"
        "- completed: 2026-07-02\n\n"
        "Done.\n"
    )


def test_present_when_file_exists(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x")
    assert probe_path(tmp_path, "src/a.py").result is ProbeResult.PRESENT


def test_absent_when_file_missing(tmp_path: Path):
    assert probe_path(tmp_path, "src/a.py").result is ProbeResult.ABSENT


def test_unknown_for_escaping_path(tmp_path: Path):
    """`../` cannot be evidence about this project -- it is not absent, it is unprobeable."""
    assert probe_path(tmp_path, "../secrets.py").result is ProbeResult.UNKNOWN


def test_unknown_for_absolute_path(tmp_path: Path):
    assert probe_path(tmp_path, "/etc/passwd").result is ProbeResult.UNKNOWN


def test_probe_records_what_was_tested(tmp_path: Path):
    probe = probe_path(tmp_path, "src/a.py")
    assert probe.target == "src/a.py"
    assert "src/a.py" in probe.detail


def test_directory_counts_as_present(tmp_path: Path):
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    assert probe_path(tmp_path, "src/pkg").result is ProbeResult.PRESENT


def test_task_done_when_in_done_dir(tmp_path: Path):
    _write_done_task(tmp_path, "t254")
    assert resolve_task(tmp_path, "t254") is TaskState.DONE


def test_task_active_when_named_in_active_file(tmp_path: Path):
    _write_active_task(tmp_path, "t254")
    assert resolve_task(tmp_path, "t254") is TaskState.ACTIVE


def test_task_missing_when_nowhere(tmp_path: Path):
    (tmp_path / "tasks" / "active").mkdir(parents=True)
    assert resolve_task(tmp_path, "t254") is TaskState.MISSING


def test_duplicate_active_and_done_task_is_rejected(tmp_path: Path):
    _write_done_task(tmp_path, "t254")
    _write_active_task(tmp_path, "t254")

    with pytest.raises(ValueError, match="duplicate task id t254"):
        resolve_task(tmp_path, "t254")


def test_task_id_is_matched_whole(tmp_path: Path):
    """t25 must not match t254."""
    _write_done_task(tmp_path, "t254")
    assert resolve_task(tmp_path, "t25") is TaskState.MISSING
