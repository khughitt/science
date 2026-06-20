"""Theme-kind apply happy-path integration tests."""

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
    """Create a minimal commons repo with themes/ and .migrations/."""
    commons = tmp_path / "commons"
    commons.mkdir()
    (commons / "themes").mkdir()
    (commons / ".migrations").mkdir()
    _init_repo(commons)
    subprocess.run(
        ["git", "-C", str(commons), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        capture_output=True,
    )
    return commons


def test_theme_apply_happy_path_creates_theme_tag(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_THEME,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj = _copy_fixture(tmp_path, "proj-alpha")
    for name in ("cross-biological.md", "malformed-scope.md", "cross-conflict.md"):
        (proj / "doc" / "themes" / name).unlink()
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(proj), "commit", "-q", "-m", "trim"],
        check=True,
        capture_output=True,
    )
    commons = _init_commons(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-alpha"], PROMOTE_KIND_THEME)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_THEME)
    assert [d.slug for d in plan.decisions] == ["cross-no-conflict"]
    result = apply_promote(plan, commons_root=commons, invocation="test")

    assert (commons / "themes" / "cross-no-conflict.md").exists()
    assert not (commons / "themes" / "project-scope.md").exists()
    assert "theme/cross-no-conflict/1.0.0" in result.tags_created
    overlay = (proj / "doc" / "themes" / "cross-no-conflict.md").read_text(
        encoding="utf-8"
    )
    assert "overlay_of: theme:cross-no-conflict" in overlay
