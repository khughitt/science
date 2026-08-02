import dataclasses
from pathlib import Path

import pytest

from science_tool.annotation.planned_edits import (
    PlannedFileEdit,
    changed_and_noop_paths,
    current_text,
    plan_update,
    sha256_text,
)


def test_current_text_preserves_crlf(tmp_path: Path):
    """`Path.read_text()` applies universal-newline translation, which would rewrite bytes
    the edit never intended -- and the round-trip guard would then certify the rewrite as
    correct. The preserving reader at entities.py:1920-1923 is the precedent."""
    target = tmp_path / "record.md"
    target.write_bytes(b"---\r\nid: proposition:x\r\n---\r\nbody\r\n")

    assert current_text(target) == "---\r\nid: proposition:x\r\n---\r\nbody\r\n"


def test_plan_update_reports_unchanged_when_text_matches(tmp_path: Path):
    target = tmp_path / "record.md"
    target.write_text("same\n", encoding="utf-8")

    edit = plan_update(target, "same\n", "noop")

    assert edit.changed is False
    assert edit.before_sha256 == edit.after_sha256 == sha256_text("same\n")


def test_changed_and_noop_paths_partitions(tmp_path: Path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("one\n", encoding="utf-8")
    b.write_text("two\n", encoding="utf-8")

    changed, noop = changed_and_noop_paths(
        [plan_update(a, "ONE\n", "r"), plan_update(b, "two\n", "r")]
    )

    assert changed == (a.as_posix(),)
    assert noop == (b.as_posix(),)


def test_planned_file_edit_is_frozen(tmp_path: Path):
    """A planner that could mutate an edit after constructing it could desynchronize
    final_text from after_sha256, and the drift check added in Task 6 reads both."""
    target = tmp_path / "a.md"
    target.write_text("x\n", encoding="utf-8")
    edit = plan_update(target, "y\n", "r")

    assert isinstance(edit, PlannedFileEdit)
    with pytest.raises(dataclasses.FrozenInstanceError):
        edit.final_text = "z\n"  # type: ignore[misc]
