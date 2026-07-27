from pathlib import Path

import pytest

from science_tool.correspondence.extract import Deliverable, Polarity
from science_tool.correspondence.probe import (
    ProbeResult,
    TaskState,
    probe_path,
    resolve_task,
)


def _create(path: str) -> Deliverable:
    return Deliverable(path=path, polarity=Polarity.CREATE)


def _remove(path: str) -> Deliverable:
    return Deliverable(path=path, polarity=Polarity.REMOVE)


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
    assert probe_path(tmp_path, _create("src/a.py")).result is ProbeResult.PRESENT


def test_absent_when_file_missing(tmp_path: Path):
    assert probe_path(tmp_path, _create("src/a.py")).result is ProbeResult.ABSENT


def test_unknown_for_escaping_path(tmp_path: Path):
    """`../` cannot be evidence about this project -- it is not absent, it is unprobeable."""
    assert probe_path(tmp_path, _create("../secrets.py")).result is ProbeResult.UNKNOWN


def test_unknown_for_absolute_path(tmp_path: Path):
    assert probe_path(tmp_path, _create("/etc/passwd")).result is ProbeResult.UNKNOWN


def test_probe_records_what_was_tested(tmp_path: Path):
    probe = probe_path(tmp_path, _create("src/a.py"))
    assert probe.target == "src/a.py"
    assert "src/a.py" in probe.detail


def test_directory_counts_as_present(tmp_path: Path):
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    assert probe_path(tmp_path, _create("src/pkg")).result is ProbeResult.PRESENT


def test_task_done_when_in_done_dir(tmp_path: Path):
    _write_done_task(tmp_path, "t254")
    assert resolve_task(tmp_path, "t254") is TaskState.DONE


def test_task_active_when_named_in_active_file(tmp_path: Path):
    _write_active_task(tmp_path, "t254")
    assert resolve_task(tmp_path, "t254") is TaskState.ACTIVE


def test_a_bare_mention_is_not_a_declaration(tmp_path: Path):
    """A prose or `related:` mention of t254 inside another task is not t254 being declared."""
    path = tmp_path / "tasks" / "active" / "t999-other.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\n"
        "id: t999\n"
        "title: Other\n"
        "priority: P1\n"
        "status: active\n"
        "aspects: []\n"
        "related:\n"
        "- task:t254\n"
        "created: 2026-07-01\n"
        "---\n\n"
        "Mentions task:t254 in prose too.\n"
    )
    assert resolve_task(tmp_path, "t254") is TaskState.MISSING


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
    """Terminal records live in tasks/done/YYYY-MM.md rollups."""
    _rollup(tmp_path)
    assert resolve_task(tmp_path, "t254") is TaskState.DONE


def test_retired_task_is_unknown_not_done(tmp_path: Path):
    """Abandonment is off the progress axis; reading it as done would manufacture completion."""
    _rollup(tmp_path)
    assert resolve_task(tmp_path, "t255") is TaskState.UNKNOWN


def test_active_status_in_active_file_is_active(tmp_path: Path):
    _write_active_task(tmp_path, "t300")
    assert resolve_task(tmp_path, "t300") is TaskState.ACTIVE


def test_a_task_block_in_done_that_is_not_terminal_is_active(tmp_path: Path):
    """The status field is the record, not which file the block happens to sit in."""
    (tmp_path / "tasks" / "done").mkdir(parents=True)
    (tmp_path / "tasks" / "done" / "2026-07.md").write_text(
        "## [t301] Half-filed\n- priority: P1\n- status: active\n- created: 2026-07-01\n\nBody.\n"
    )
    assert resolve_task(tmp_path, "t301") is TaskState.ACTIVE


def test_status_line_in_a_description_is_not_read_as_a_field(tmp_path: Path):
    """Active status comes from frontmatter, not a lookalike line in the body."""
    path = tmp_path / "tasks" / "active" / "t302-do-it.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\n"
        "id: t302\n"
        "title: Do it\n"
        "priority: P1\n"
        "status: active\n"
        "aspects: []\n"
        "created: 2026-07-01\n"
        "---\n\n"
        "Notes below:\n- status: done\n"
    )
    assert resolve_task(tmp_path, "t302") is TaskState.ACTIVE


# --- fb-2026-07-26-014: a removal deliverable is scored in the direction it is measured ---


def test_a_removal_target_that_is_gone_satisfies_the_plan(tmp_path: Path):
    """`absent` IS the exit criterion for a retirement plan; scoring it as
    unbuilt read such a plan exactly backwards."""
    probe = probe_path(tmp_path, _remove("src/old.ts"))
    assert probe.result is ProbeResult.PRESENT
    assert probe.polarity is Polarity.REMOVE


def test_a_removal_target_still_on_disk_does_not_satisfy_the_plan(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "old.ts").write_text("x")
    assert probe_path(tmp_path, _remove("src/old.ts")).result is ProbeResult.ABSENT


def test_a_removal_probe_names_its_polarity_in_the_evidence_line(tmp_path: Path):
    assert "declared for removal" in probe_path(tmp_path, _remove("src/old.ts")).detail


def test_an_unprobeable_removal_target_is_still_unknown(tmp_path: Path):
    """Polarity cannot rescue a path the instrument could not test."""
    assert probe_path(tmp_path, _remove("../outside.py")).result is ProbeResult.UNKNOWN
