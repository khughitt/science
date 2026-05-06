"""Ordered migration runner: walk steps; on failure, abort + restore snapshot."""

import subprocess
from pathlib import Path

from science_tool.project_artifacts.migrations import (
    run_migration,
)
from science_tool.project_artifacts.migrations.transaction import TempCommitSnapshot
from science_tool.project_artifacts.registry_schema import MigrationStep


def _bash_step(id_: str, check: str, apply: str) -> MigrationStep:
    return MigrationStep.model_validate(
        {
            "id": id_,
            "description": id_,
            "touched_paths": ["a.txt"],
            "reversible": False,
            "idempotent": True,
            "impl": {
                "kind": "bash",
                "shell": "bash",
                "working_dir": ".",
                "timeout_seconds": 5,
                "check": check,
                "apply": apply,
            },
        }
    )


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "f.txt").write_text("init", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)


def test_all_pass_happy_path(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    snap = TempCommitSnapshot(tmp_path)
    snap.take()

    steps = [
        _bash_step("s1", check="test -f a.txt && exit 0 || exit 1\n", apply="touch a.txt\n"),
        _bash_step("s2", check="test -f b.txt && exit 0 || exit 1\n", apply="touch b.txt\n"),
    ]
    result = run_migration(steps, tmp_path, snap, auto_apply=True)
    assert result.all_succeeded
    assert {r.step_id for r in result.steps if r.action == "applied"} == {"s1", "s2"}


def test_idempotent_step_reruns_as_no_op(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("already", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "--amend", "--no-edit"], cwd=tmp_path, check=True)
    snap = TempCommitSnapshot(tmp_path)
    snap.take()
    steps = [_bash_step("s1", check="test -f a.txt && exit 0 || exit 1\n", apply="touch a.txt\n")]
    result = run_migration(steps, tmp_path, snap, auto_apply=True)
    assert result.steps[0].action == "skipped"


def test_failure_mid_run_restores_snapshot(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    snap = TempCommitSnapshot(tmp_path)
    snap.take()
    steps = [
        _bash_step("s1", check="test -f a.txt && exit 0 || exit 1\n", apply="touch a.txt\n"),
        _bash_step("s2-fails", check="exit 1\n", apply="exit 1\n"),  # apply fails
    ]
    result = run_migration(steps, tmp_path, snap, auto_apply=True)
    assert not result.all_succeeded
    assert not (tmp_path / "a.txt").exists()  # snapshot restored
