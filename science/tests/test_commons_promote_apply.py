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


def _build_project(tmp_path: Path, name: str, papers: dict[str, str]) -> Path:
    """Create a project repo at `tmp_path/<name>` with paper files at `doc/papers/`."""
    root = tmp_path / name
    (root / "doc" / "papers").mkdir(parents=True)
    for filename, content in papers.items():
        (root / "doc" / "papers" / filename).write_text(content, encoding="utf-8")
    _init_repo(root)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)
    return root


def test_apply_promote_happy_path_writes_commits_tags_rewrites(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\nyear: 2025\n---\n\n## Key Findings\n\nfoo\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-a": proj}[slug],
    )

    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])

    result = apply_promote(plan, commons_root=tmp_path / "commons",
                           invocation="science commons promote paper --from proj-a --apply")

    assert result.status == "ok"
    assert result.commons_commit is not None
    assert result.tags_created == ["paper/Adams2025/1.0.0"]
    canon = tmp_path / "commons" / "papers" / "Adams2025.md"
    assert canon.exists()
    canon_text = canon.read_text(encoding="utf-8")
    assert "schema_profile: science-entity-base/1.0+paper/2.0" in canon_text
    assert "## Key Findings" in canon_text
    overlay = proj / "doc" / "papers" / "Adams2025.md"
    overlay_text = overlay.read_text(encoding="utf-8")
    assert "overlay_of: paper:Adams2025" in overlay_text
    assert 'pin_version: "1.0.0"' in overlay_text
    assert result.audit_log_path is not None
    assert result.audit_log_path.exists()
    log_data = yaml.safe_load(result.audit_log_path.read_text(encoding="utf-8"))
    assert log_data["status"] == "ok"


def test_apply_promote_preflight_rejects_dirty_commons(tmp_path, monkeypatch) -> None:
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    (tmp_path / "commons" / "dirty.txt").write_text("WIP\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path / "commons"), "add", "--", "dirty.txt"], check=True)

    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])
    with pytest.raises(PromoteInputError, match="commons"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")


def test_apply_promote_preflight_rejects_dirty_target_project_file(tmp_path, monkeypatch) -> None:
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    (proj / "doc" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntitle: DIRTY\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])
    with pytest.raises(PromoteInputError, match="dirty"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")


def test_apply_promote_preflight_allows_dirty_non_target_project_file(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    (proj / "other.md").write_text("dirty\n", encoding="utf-8")

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])
    result = apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")
    assert result.status == "ok"


def test_apply_promote_idempotent_skips_already_overlayed(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery1 = discover_paper_candidates(["proj-a"])
    plan1 = plan_promote(discovery1, commons_root=tmp_path / "commons",
                         resolve_conflict=lambda c: None, from_order=["proj-a"])
    apply_promote(plan1, commons_root=tmp_path / "commons", invocation="first")
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-q", "-m", "promote"], check=True)
    discovery2 = discover_paper_candidates(["proj-a"])
    assert discovery2.candidates_by_bibkey == {}
    plan2 = plan_promote(discovery2, commons_root=tmp_path / "commons",
                         resolve_conflict=lambda c: None, from_order=["proj-a"])
    assert plan2.decisions == []
    head_before = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    result2 = apply_promote(plan2, commons_root=tmp_path / "commons", invocation="second")
    assert result2.status == "ok"
    assert result2.commons_commit is None
    assert result2.tags_created == []
    assert result2.audit_log_path is None
    head_after = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert head_before == head_after


def test_apply_promote_rename_happy_path_unlinks_source_writes_target(tmp_path, monkeypatch) -> None:
    """When --from order forces canonical case `Huh2024` but proj-b has
    `huh2024.md`, apply must (1) write target `Huh2024.md`, (2) unlink
    `huh2024.md`, and record the rename in the audit log."""
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj_a = _build_project(
        tmp_path, "proj-a",
        {"Huh2024.md": "---\nid: paper:Huh2024\ntitle: H\n---\n"},
    )
    proj_b = _build_project(
        tmp_path, "proj-b",
        {"huh2024.md": "---\nid: paper:huh2024\ntitle: H\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-a": proj_a, "proj-b": proj_b}[slug],
    )

    discovery = discover_paper_candidates(["proj-a", "proj-b"])
    plan = plan_promote(
        discovery, commons_root=tmp_path / "commons",
        resolve_conflict=lambda c: None, from_order=["proj-a", "proj-b"],
    )
    assert plan.decisions[0].bibkey == "Huh2024"
    result = apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")
    assert result.status == "ok"
    assert not (proj_b / "doc" / "papers" / "huh2024.md").exists()
    assert (proj_b / "doc" / "papers" / "Huh2024.md").exists()
    assert (proj_a / "doc" / "papers" / "Huh2024.md").exists()
    log = yaml.safe_load(result.audit_log_path.read_text(encoding="utf-8"))
    proj_b_rewrites = log["projects_touched"]["proj-b"]["overlay_rewrites"]
    assert proj_b_rewrites[0]["rename"] == {"from": "huh2024.md", "to": "Huh2024.md"}


def test_apply_promote_rename_collision_aborts(tmp_path, monkeypatch) -> None:
    """If the canonical-case target already exists in the project (an unrelated
    file shares the case-folded name), promote refuses to clobber it."""
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj_a = _build_project(
        tmp_path, "proj-a",
        {"Huh2024.md": "---\nid: paper:Huh2024\ntitle: H\n---\n"},
    )
    proj_b = _build_project(
        tmp_path, "proj-b",
        {
            "huh2024.md": "---\nid: paper:huh2024\ntitle: H\n---\n",
            "Huh2024.md": "---\nid: paper:Huh2024\ntitle: H (different file)\n---\n",
        },
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-a": proj_a, "proj-b": proj_b}[slug],
    )

    discovery = discover_paper_candidates(["proj-a", "proj-b"])
    with pytest.raises(PromoteInputError, match="case-rename collision"):
        plan_promote(
            discovery, commons_root=tmp_path / "commons",
            resolve_conflict=lambda c: None, from_order=["proj-a", "proj-b"],
        )


def test_apply_promote_tag_preflight_rejects_existing_tag(tmp_path, monkeypatch) -> None:
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    subprocess.run(["git", "-C", str(tmp_path / "commons"), "tag", "paper/Adams2025/1.0.0"], check=True)

    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])
    with pytest.raises(PromoteWriteError, match="tag"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")


def test_apply_promote_step4_os_error_converts_to_promote_write_error(
    tmp_path, monkeypatch,
) -> None:
    """A PermissionError / disk-full OSError while writing canonical files in
    step 4 must be converted to PromoteWriteError(stage="write_commons") so
    the outer failure-audit path runs (design §6.4 "Before step 5" recovery).
    The raw OSError must NOT propagate, and no partial canonicals should be
    left on disk."""
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        apply_promote,
        discover_paper_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path, "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_paper_candidates(["proj-a"])
    plan = plan_promote(discovery, commons_root=tmp_path / "commons",
                        resolve_conflict=lambda c: None, from_order=["proj-a"])

    # Force write_text to fail at step 4 by making the commons papers/ dir
    # read-only AFTER plan_promote has finished.
    papers_dir = tmp_path / "commons" / "papers"
    papers_dir.chmod(0o555)
    try:
        with pytest.raises(PromoteWriteError, match="canonical write failed"):
            apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")
    finally:
        papers_dir.chmod(0o755)

    # No partial canonical left on disk:
    assert not (papers_dir / "Adams2025.md").exists()
    # Failure audit log was written (uncommitted):
    logs = list((tmp_path / "commons" / ".migrations").glob("*.yaml"))
    assert logs, "failure audit log should have been written"
    data = yaml.safe_load(logs[0].read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert data["failure_stage"] == "write_commons"
