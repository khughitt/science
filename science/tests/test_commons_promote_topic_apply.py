"""Topic-kind apply integration tests, including the flatten path."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

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


def test_topic_apply_flatten_unlinks_background_source(tmp_path, monkeypatch) -> None:
    """A topic sourced from doc/background/topics/ is relocated to overlays/topics/."""
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

    assert (proj / "overlays" / "topics" / "flatten-source.md").exists()
    assert not (proj / "doc" / "background" / "topics" / "flatten-source.md").exists()
    assert result.audit_log_path is not None
    log = yaml.safe_load(result.audit_log_path.read_text(encoding="utf-8"))
    rewrites = log["projects_touched"]["proj-alpha"]["overlay_rewrites"]
    flatten_entry = next(entry for entry in rewrites if entry["slug"] == "flatten-source")
    assert flatten_entry["path"] == str(proj / "overlays" / "topics" / "flatten-source.md")
    assert flatten_entry["unlinked_source"] == str(proj / "doc" / "background" / "topics" / "flatten-source.md")


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


def test_topic_apply_rollback_restores_unlinked_source(tmp_path, monkeypatch) -> None:
    """A later overlay failure restores an earlier unlinked background source."""
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj = _copy_fixture(tmp_path, "proj-alpha")
    for path in (proj / "entities" / "topics").glob("*.md"):
        if path.name != "single-instance.md":
            path.unlink()
    for path in (proj / "doc" / "background" / "topics").glob("*.md"):
        if path.name != "flatten-source.md":
            path.unlink()
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

    discovery = discover_candidates(["proj-alpha"], PROMOTE_KIND_TOPIC)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_TOPIC)

    failing_target = proj / "overlays" / "topics" / "single-instance.md"
    real_write_text = Path.write_text

    def sabotaged_write_text(self: Path, *args, **kwargs):
        if self == failing_target:
            raise OSError("simulated project overlay write failure")
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", sabotaged_write_text)

    with pytest.raises(PromoteWriteError, match="overlay write"):
        apply_promote(plan, commons_root=commons, invocation="test")

    assert (proj / "doc" / "background" / "topics" / "flatten-source.md").exists()


