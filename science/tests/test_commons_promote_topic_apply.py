"""Topic-kind apply integration tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "promote"


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@x"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", "test"],
        check=True,
        capture_output=True,
    )


def _copy_fixture(tmp_path: Path, project: str) -> Path:
    """Copy a fixture project into a temp dir and initialize a git repo."""
    dst = tmp_path / project
    shutil.copytree(FIXTURES / project, dst)
    _init_repo(dst)
    subprocess.run(["git", "-C", str(dst), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(dst), "commit", "-q", "-m", "init"],
        check=True,
        capture_output=True,
    )
    return dst


def _init_commons(tmp_path: Path) -> Path:
    """Create a minimal commons repo with topics/ and .migrations/."""
    commons = tmp_path / "commons"
    commons.mkdir()
    (commons / "topics").mkdir()
    (commons / ".migrations").mkdir()
    _init_repo(commons)
    subprocess.run(
        ["git", "-C", str(commons), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        capture_output=True,
    )
    return commons


def test_topic_apply_commons_tag_uses_topic_prefix(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj = _copy_fixture(tmp_path, "proj-alpha")
    commons = _init_commons(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_TOPIC)
    result = apply_promote(plan, commons_root=commons, invocation="test")

    assert any(t.startswith("topic/") for t in result.tags_created)
    assert not any(t.startswith("paper/") for t in result.tags_created)
