"""Tests for science_tool.commons.promote — apply phase, audit log, rollback."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@x"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "test"], check=True)


def _init_commons(root: Path) -> None:
    _init_repo(root)
    (root / "papers").mkdir()
    (root / ".migrations").mkdir()
    (root / ".gitignore").write_text("registry.sqlite\n.registry-*.sqlite\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)


def test_write_audit_log_writes_yaml_with_expected_shape(tmp_path) -> None:
    from science_tool.commons.promote import (
        PromoteResult,
        _write_audit_log,
    )

    _init_commons(tmp_path)
    result = PromoteResult(
        op_id="7a3f2c91",
        started_at=datetime(2026, 5, 15, 14, 30, 11, tzinfo=timezone.utc),
        finished_at=datetime(2026, 5, 15, 14, 30, 47, tzinfo=timezone.utc),
        commons_commit="abc1234",
        tags_created=["paper/Adams2025/1.0.0"],
        decisions=[],
        failed_candidates=[],
        audit_log_path=None,
        status="ok",
        failure_stage=None,
        failure_detail=None,
        projects_touched=[],
    )
    path = _write_audit_log(result, tmp_path, invocation="science commons promote paper --apply")
    assert path.exists()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["op_id"] == "7a3f2c91"
    assert data["status"] == "ok"
    assert data["commons_commit"] == "abc1234"
    assert data["commons_tags"] == ["paper/Adams2025/1.0.0"]
    assert "rollback" in data


def test_rollback_step5_deletes_tags_and_restores_path_limited(tmp_path) -> None:
    from science_tool.commons.promote import _rollback_step5

    _init_commons(tmp_path)
    canon = tmp_path / "papers" / "Adams2025.md"
    canon.write_text("---\nid: paper:Adams2025\n---\nbody\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", "papers/Adams2025.md"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "promote test"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "tag", "paper/Adams2025/1.0.0"], check=True)

    (tmp_path / "unrelated.txt").write_text("dirty work\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", "unrelated.txt"], check=True)

    _rollback_step5(
        commons_root=tmp_path,
        tags_attempted=["paper/Adams2025/1.0.0"],
        canonical_paths=[canon],
    )

    tags = subprocess.run(
        ["git", "-C", str(tmp_path), "tag"], capture_output=True, text=True, check=True
    ).stdout.split()
    assert "paper/Adams2025/1.0.0" not in tags
    assert not canon.exists()
    status = subprocess.run(
        ["git", "-C", str(tmp_path), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "A  unrelated.txt" in status


def test_rollback_step5_restores_re_promote_file(tmp_path) -> None:
    """For an existing canonical file (re-promote), checkout HEAD -- <path>
    restores the prior content."""
    from science_tool.commons.promote import _rollback_step5

    _init_commons(tmp_path)
    canon = tmp_path / "papers" / "X.md"
    canon.write_text("original\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", "papers/X.md"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "v1"], check=True)
    canon.write_text("promoted v2\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", "papers/X.md"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "promote"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "tag", "paper/X/1.1.0"], check=True)

    _rollback_step5(
        commons_root=tmp_path,
        tags_attempted=["paper/X/1.1.0"],
        canonical_paths=[canon],
    )

    assert canon.exists()
    assert canon.read_text(encoding="utf-8") == "original\n"
