from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from science_model.autonomous_runs import RunTier

from science_tool.autonomy import lifecycle as lifecycle_module
from science_tool.autonomy.git import worktree_status
from science_tool.autonomy.lifecycle import RepositoryStateError, start_run


def _start(project: Path, baseline_out: Path):
    return start_run(
        project, agent="health-audit", model="deterministic", tier=RunTier.REPORT_ONLY,
        short_id="a1b2", started=datetime(2026, 8, 2, 9, 0, tzinfo=UTC),
        baseline_out=baseline_out,
    )


def test_start_leaves_no_materialization_residue(ungraphed_project: Path, tmp_path: Path):
    """Design §1.1: `_capture` materializes into the project, and a supervisor that then
    stages the actor's output sweeps its own write into the actor's attested range."""
    _start(ungraphed_project, tmp_path / "state" / "baseline.json")

    assert worktree_status(ungraphed_project) == ""


def test_start_removes_its_residue_when_it_raises(
    ungraphed_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The postcondition must survive the error paths: `start_run` can raise four more times
    after materializing, and residue left behind blocks the NEXT run rather than this one."""
    real_capture = lifecycle_module._capture

    def _capture_then_fail(project_root: Path):
        real_capture(project_root)
        raise RuntimeError("capture blew up after materializing")

    monkeypatch.setattr(lifecycle_module, "_capture", _capture_then_fail)

    with pytest.raises(RuntimeError):
        _start(ungraphed_project, tmp_path / "state" / "baseline.json")

    assert worktree_status(ungraphed_project) == ""


def test_a_dirty_input_tree_is_refused_byte_for_byte_unchanged(
    ungraphed_project: Path, tmp_path: Path
):
    """Design §4.1: the postcondition begins AFTER `assert_repository_is_at` succeeds. On the
    one path where the tree is legitimately dirty, the dirt is the CALLER's."""
    tracked = ungraphed_project / "entities" / "propositions" / "p1.md"
    tracked.write_text(tracked.read_text(encoding="utf-8") + "\nEdited.\n", encoding="utf-8")
    untracked = ungraphed_project / "entities" / "propositions" / "p2.md"
    untracked.write_text("---\nid: proposition:p2\nkind: proposition\ntitle: P2\n---\n", encoding="utf-8")
    before = (tracked.read_text(encoding="utf-8"), untracked.read_text(encoding="utf-8"))

    with pytest.raises(RepositoryStateError):
        _start(ungraphed_project, tmp_path / "state" / "baseline.json")

    assert tracked.exists() and untracked.exists()
    assert (tracked.read_text(encoding="utf-8"), untracked.read_text(encoding="utf-8")) == before
