from pathlib import Path

from science_tool.correspondence.probe import (
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


def _block(task_id: str, status: str) -> str:
    return f"## [{task_id}] Thing\n- priority: P1\n- status: {status}\n- created: 2026-07-01\n\nBody.\n"


def test_task_done_when_a_done_block_lives_in_a_per_task_file(tmp_path: Path):
    """`done/*.md` is searched whatever it is named -- but the BLOCK is the record."""
    (tmp_path / "tasks" / "done").mkdir(parents=True)
    (tmp_path / "tasks" / "done" / "t254-thing.md").write_text(_block("t254", "done"))
    assert resolve_task(tmp_path, "t254") is TaskState.DONE


def test_task_active_when_declared_in_active_file(tmp_path: Path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(_block("t254", "active"))
    assert resolve_task(tmp_path, "t254") is TaskState.ACTIVE


def test_a_bare_mention_is_not_a_declaration(tmp_path: Path):
    """A prose or `related:` mention of t254 inside another task is not t254 being declared."""
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t999] Other\n- priority: P1\n- status: active\n- related: [task:t254]\n"
        "- created: 2026-07-01\n\nMentions task:t254 in prose too.\n"
    )
    assert resolve_task(tmp_path, "t254") is TaskState.MISSING


def test_task_missing_when_nowhere(tmp_path: Path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(_block("t999", "active"))
    assert resolve_task(tmp_path, "t254") is TaskState.MISSING


def test_a_duplicated_id_resolves_to_the_less_complete_record(tmp_path: Path):
    """A duplicated id is a project defect. Preferring `active.md` refuses to manufacture
    completion from an ambiguous record, and matches `find_task_location`'s precedence."""
    (tmp_path / "tasks" / "done").mkdir(parents=True)
    (tmp_path / "tasks" / "done" / "2026-07.md").write_text(_block("t254", "done"))
    (tmp_path / "tasks" / "active.md").write_text(_block("t254", "active"))
    assert resolve_task(tmp_path, "t254") is TaskState.ACTIVE


def test_task_id_is_matched_whole(tmp_path: Path):
    """t25 must not be satisfied by t254's block."""
    (tmp_path / "tasks" / "done").mkdir(parents=True)
    (tmp_path / "tasks" / "done" / "2026-07.md").write_text(_block("t254", "done"))
    assert resolve_task(tmp_path, "t254") is TaskState.DONE
    assert resolve_task(tmp_path, "t25") is TaskState.MISSING


# --- fb-2026-07-26-013: the record is the task block, not the filename ---

_ROLLUP = """# Done — 2026-07

## [t254] Ship the thing
- priority: P1
- status: done
- created: 2026-07-01
- completed: 2026-07-19

It shipped.

## [t255] Abandon the other thing
- priority: P2
- status: retired
- created: 2026-07-01
- completed: 2026-07-20

Not doing it.
"""


def _rollup(root: Path) -> None:
    (root / "tasks" / "done").mkdir(parents=True)
    (root / "tasks" / "done" / "2026-07.md").write_text(_ROLLUP)


def test_task_done_when_filed_in_a_month_rollup(tmp_path: Path):
    """`tasks_archive` routes terminal entries to tasks/done/YYYY-MM.md, not one file per task."""
    _rollup(tmp_path)
    assert resolve_task(tmp_path, "t254") is TaskState.DONE


def test_retired_task_is_unknown_not_done(tmp_path: Path):
    """Abandonment is off the progress axis; reading it as done would manufacture completion."""
    _rollup(tmp_path)
    assert resolve_task(tmp_path, "t255") is TaskState.UNKNOWN


def test_active_status_in_active_ledger_is_active(tmp_path: Path):
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t300] Do it\n- priority: P1\n- status: active\n- created: 2026-07-01\n\nBody.\n"
    )
    assert resolve_task(tmp_path, "t300") is TaskState.ACTIVE


def test_a_task_block_in_done_that_is_not_terminal_is_active(tmp_path: Path):
    """The status field is the record, not which file the block happens to sit in."""
    (tmp_path / "tasks" / "done").mkdir(parents=True)
    (tmp_path / "tasks" / "done" / "2026-07.md").write_text(
        "## [t301] Half-filed\n- priority: P1\n- status: active\n- created: 2026-07-01\n\nBody.\n"
    )
    assert resolve_task(tmp_path, "t301") is TaskState.ACTIVE


def test_status_line_in_a_description_is_not_read_as_a_field(tmp_path: Path):
    """Fields are the contiguous block after the header; prose below it is description."""
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t302] Do it\n- priority: P1\n- status: active\n- created: 2026-07-01\n\n"
        "Notes below:\n- status: done\n"
    )
    assert resolve_task(tmp_path, "t302") is TaskState.ACTIVE
