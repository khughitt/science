from pathlib import Path

from science_tool.drift_sample.probe import (
    ProbeResult,
    TaskState,
    probe_path,
    resolve_task,
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
    (tmp_path / "tasks" / "done").mkdir(parents=True)
    (tmp_path / "tasks" / "done" / "t254-thing.md").write_text("x")
    assert resolve_task(tmp_path, "t254") is TaskState.DONE


def test_task_active_when_named_in_active_file(tmp_path: Path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text("- task:t254 do the thing\n")
    assert resolve_task(tmp_path, "t254") is TaskState.ACTIVE


def test_task_missing_when_nowhere(tmp_path: Path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text("- task:t999\n")
    assert resolve_task(tmp_path, "t254") is TaskState.MISSING


def test_done_wins_over_active(tmp_path: Path):
    """A task both filed done and left in active.md is done; the file is the record."""
    (tmp_path / "tasks" / "done").mkdir(parents=True)
    (tmp_path / "tasks" / "done" / "t254-x.md").write_text("x")
    (tmp_path / "tasks" / "active.md").write_text("- task:t254\n")
    assert resolve_task(tmp_path, "t254") is TaskState.DONE


def test_task_id_is_matched_whole(tmp_path: Path):
    """t25 must not match t254."""
    (tmp_path / "tasks" / "done").mkdir(parents=True)
    (tmp_path / "tasks" / "done" / "t254-x.md").write_text("x")
    assert resolve_task(tmp_path, "t25") is TaskState.MISSING
