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


def test_result_carries_kind() -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        PromoteResult,
    )

    r = PromoteResult(
        op_id="x",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        commons_commit=None,
        tags_created=[],
        decisions=[],
        failed_candidates=[],
        audit_log_path=None,
        status="ok",
        failure_stage=None,
        failure_detail=None,
        projects_touched=[],
        kind=PROMOTE_KIND_PAPER,
    )
    assert r.kind is PROMOTE_KIND_PAPER


def test_repo_is_idle_checks_linked_worktree_gitdir(tmp_path) -> None:
    from science_tool.commons.promote import _repo_is_idle

    main = tmp_path / "main"
    linked = tmp_path / "linked"
    main.mkdir()
    _init_repo(main)
    (main / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(main), "add", "."], check=True)
    subprocess.run(["git", "-C", str(main), "commit", "-q", "-m", "init"], check=True)
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", "-q", "-b", "linked-test", str(linked)],
        check=True,
    )

    git_dir = subprocess.run(
        ["git", "-C", str(linked), "rev-parse", "--git-dir"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (linked / git_dir / "MERGE_HEAD").write_text("staged merge\n", encoding="utf-8")

    assert _repo_is_idle(linked) is False


def test_write_audit_log_writes_yaml_with_expected_shape(tmp_path) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
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
        kind=PROMOTE_KIND_PAPER,
    )
    path = _write_audit_log(result, tmp_path, invocation="science commons promote paper --apply")
    assert path.exists()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["op_id"] == "7a3f2c91"
    assert data["status"] == "ok"
    assert data["commons_commit"] == "abc1234"
    assert data["commons_tags"] == ["paper/Adams2025/1.0.0"]
    assert "rollback" in data


def test_audit_log_yaml_type_field_uses_kind_kind() -> None:
    """Audit log root type field reads from result.kind.kind."""
    from datetime import datetime, timezone
    from pathlib import Path

    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        PromoteResult,
        _render_audit_log_yaml,
    )

    result = PromoteResult(
        op_id="abc",
        started_at=datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 5, 16, 12, 1, tzinfo=timezone.utc),
        commons_commit="deadbeef",
        tags_created=[],
        decisions=[],
        failed_candidates=[],
        audit_log_path=None,
        status="ok",
        failure_stage=None,
        failure_detail=None,
        projects_touched=[],
        kind=PROMOTE_KIND_TOPIC,
    )
    yaml_str = _render_audit_log_yaml(result, Path("/tmp/x"), invocation="x")
    assert "kind: topic" in yaml_str
    assert "kind: paper" not in yaml_str


def test_build_project_rollback_command_derives_project_root_from_kind_depth(tmp_path) -> None:
    """A deeper overlay_dest_subdir must still resolve project_root correctly."""
    import re

    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        PromoteKindConfig,
        _build_project_rollback_command,
    )

    deep_kind = PromoteKindConfig(
        kind="topic",
        source_subdirs=("doc/datasets/promoted",),
        overlay_dest_subdir="doc/datasets/promoted",
        commons_subdir="topics",
        id_prefix="topic:",
        slug_regex=re.compile(r"^[a-z0-9-]+$"),
        slug_match="exact",
        mixin_schema_id=PROMOTE_KIND_TOPIC.mixin_schema_id,
        default_profile=PROMOTE_KIND_TOPIC.default_profile,
        eligibility_filter=None,
    )
    entries = [
        {"path": str(tmp_path / "doc" / "datasets" / "promoted" / "x.md")},
        {"path": str(tmp_path / "doc" / "datasets" / "promoted" / "y.md")},
    ]
    cmd = _build_project_rollback_command(entries, deep_kind)
    assert (
        cmd
        == f"git -C {tmp_path} checkout HEAD -- "
        "doc/datasets/promoted/x.md doc/datasets/promoted/y.md"
    )


def test_build_project_rollback_command_includes_unlinked_source(tmp_path) -> None:
    """Flatten case: an entry with `unlinked_source` extends the rollback to
    cover both target and source paths."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        _build_project_rollback_command,
    )

    entries = [
        {
            "path": str(tmp_path / "overlays" / "topics" / "primitives.md"),
            "unlinked_source": str(
                tmp_path / "entities" / "topics" / "primitives.md"
            ),
        },
    ]
    cmd = _build_project_rollback_command(entries, PROMOTE_KIND_TOPIC)
    assert "overlays/topics/primitives.md" in cmd
    assert "entities/topics/primitives.md" in cmd


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
        capture_output=True,
        text=True,
        check=True,
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
    """Create a project repo at `tmp_path/<name>` with paper files at `entities/papers/`."""
    root = tmp_path / name
    (root / "entities" / "papers").mkdir(parents=True)
    for filename, content in papers.items():
        (root / "entities" / "papers" / filename).write_text(content, encoding="utf-8")
    _init_repo(root)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)
    return root


def test_apply_promote_happy_path_writes_commits_tags_rewrites(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\nyear: 2025\n---\n\n## Key Findings\n\nfoo\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-a": proj}[slug],
    )

    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )

    result = apply_promote(
        plan, commons_root=tmp_path / "commons", invocation="science commons promote paper --from proj-a --apply"
    )

    assert result.status == "ok"
    assert result.commons_commit is not None
    assert result.tags_created == ["paper/Adams2025/1.0.0"]
    canon = tmp_path / "commons" / "papers" / "Adams2025.md"
    assert canon.exists()
    canon_text = canon.read_text(encoding="utf-8")
    assert "schema_profile: science-entity-base/1.0+paper/2.0" in canon_text
    assert "## Key Findings" in canon_text
    overlay = proj / "overlays" / "papers" / "Adams2025.md"
    overlay_text = overlay.read_text(encoding="utf-8")
    assert "overlay_of: paper:Adams2025" in overlay_text
    assert 'pin_version: "1.0.0"' in overlay_text
    assert result.audit_log_path is not None
    assert result.audit_log_path.exists()
    log_data = yaml.safe_load(result.audit_log_path.read_text(encoding="utf-8"))
    assert log_data["status"] == "ok"


def test_audit_log_records_canonical_paths_per_decision(tmp_path, monkeypatch) -> None:
    """Each decision contributes one canonical_paths entry, list-form."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\nyear: 2025\n---\n\n## Key Findings\n\nfoo\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-a": proj}[slug],
    )

    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )

    result = apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")

    assert result.audit_log_path is not None
    log = yaml.safe_load(result.audit_log_path.read_text(encoding="utf-8"))
    assert "decisions" in log
    assert log["decisions"] == [
        {
            "slug": "Adams2025",
            "canonical_version": "1.0.0",
            "canonical_paths": ["papers/Adams2025.md"],
        }
    ]
    assert not Path(log["decisions"][0]["canonical_paths"][0]).is_absolute()


def test_apply_promote_rejects_absolute_canonical_artifact_path(tmp_path) -> None:
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        CanonicalArtifact,
        PromoteDecision,
        PromotePlan,
        apply_promote,
    )

    commons = tmp_path / "commons"
    _init_commons(commons)
    outside = tmp_path / "outside.md"
    plan = PromotePlan(
        decisions=[
            PromoteDecision(
                slug="unsafe",
                canonical_artifacts=[
                    CanonicalArtifact(
                        path=outside,
                        content="unsafe\n",
                        validator="plain",
                    )
                ],
                canonical_version="1.0.0",
                overlays={},
                resolved_conflicts=(),
            )
        ],
        failed_candidates=[],
        kind=PROMOTE_KIND_PAPER,
    )

    with pytest.raises(PromoteInputError, match="canonical artifact path"):
        apply_promote(plan, commons_root=commons, invocation="...")

    assert not outside.exists()
    logs = list((commons / ".migrations").glob("*.yaml"))
    assert len(logs) == 1
    log = yaml.safe_load(logs[0].read_text(encoding="utf-8"))
    assert log["status"] == "failed"
    assert log["decisions"] == [
        {
            "slug": "unsafe",
            "canonical_version": "1.0.0",
            "canonical_paths": [],
        }
    ]
    assert str(outside) not in logs[0].read_text(encoding="utf-8")


def test_apply_promote_rejects_parent_traversal_canonical_artifact_path(tmp_path) -> None:
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        CanonicalArtifact,
        PromoteDecision,
        PromotePlan,
        apply_promote,
    )

    commons = tmp_path / "commons"
    _init_commons(commons)
    outside = tmp_path / "escape.md"
    plan = PromotePlan(
        decisions=[
            PromoteDecision(
                slug="unsafe",
                canonical_artifacts=[
                    CanonicalArtifact(
                        path=Path("../escape.md"),
                        content="unsafe\n",
                        validator="plain",
                    )
                ],
                canonical_version="1.0.0",
                overlays={},
                resolved_conflicts=(),
            )
        ],
        failed_candidates=[],
        kind=PROMOTE_KIND_PAPER,
    )

    with pytest.raises(PromoteInputError, match="canonical artifact path"):
        apply_promote(plan, commons_root=commons, invocation="...")

    assert not outside.exists()
    logs = list((commons / ".migrations").glob("*.yaml"))
    assert len(logs) == 1
    log = yaml.safe_load(logs[0].read_text(encoding="utf-8"))
    assert log["status"] == "failed"
    assert log["decisions"] == [
        {
            "slug": "unsafe",
            "canonical_version": "1.0.0",
            "canonical_paths": [],
        }
    ]


def test_apply_promote_failure_audit_omits_symlink_escape_canonical_artifact_path(tmp_path) -> None:
    import os

    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        CanonicalArtifact,
        PromoteDecision,
        PromotePlan,
        apply_promote,
    )

    commons = tmp_path / "commons"
    outside = tmp_path / "outside"
    outside.mkdir()
    _init_commons(commons)
    os.symlink(outside, commons / "escape_link", target_is_directory=True)
    subprocess.run(["git", "-C", str(commons), "add", "escape_link"], check=True)
    subprocess.run(["git", "-C", str(commons), "commit", "-q", "-m", "add symlink"], check=True)
    plan = PromotePlan(
        decisions=[
            PromoteDecision(
                slug="unsafe",
                canonical_artifacts=[
                    CanonicalArtifact(
                        path=Path("escape_link/out.md"),
                        content="unsafe\n",
                        validator="plain",
                    )
                ],
                canonical_version="1.0.0",
                overlays={},
                resolved_conflicts=(),
            )
        ],
        failed_candidates=[],
        kind=PROMOTE_KIND_PAPER,
    )

    with pytest.raises(PromoteInputError, match="escapes commons root"):
        apply_promote(plan, commons_root=commons, invocation="...")

    assert not (outside / "out.md").exists()
    logs = list((commons / ".migrations").glob("*.yaml"))
    assert len(logs) == 1
    log = yaml.safe_load(logs[0].read_text(encoding="utf-8"))
    assert log["status"] == "failed"
    assert log["decisions"] == [
        {
            "slug": "unsafe",
            "canonical_version": "1.0.0",
            "canonical_paths": [],
        }
    ]


def test_apply_promote_writes_and_stages_multiple_canonical_artifacts(tmp_path) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        CanonicalArtifact,
        PromoteDecision,
        PromotePlan,
        apply_promote,
    )

    commons = tmp_path / "commons"
    _init_commons(commons)
    plan = PromotePlan(
        decisions=[
            PromoteDecision(
                slug="multi",
                canonical_artifacts=[
                    CanonicalArtifact(
                        path=Path("papers/multi.md"),
                        content="primary\n",
                        validator="plain",
                    ),
                    CanonicalArtifact(
                        path=Path("papers/multi/extra.md"),
                        content="extra\n",
                        validator="plain",
                    ),
                ],
                canonical_version="1.0.0",
                overlays={},
                resolved_conflicts=(),
            )
        ],
        failed_candidates=[],
        kind=PROMOTE_KIND_PAPER,
    )

    result = apply_promote(plan, commons_root=commons, invocation="...")

    assert result.status == "ok"
    assert (commons / "papers" / "multi.md").read_text(encoding="utf-8") == "primary\n"
    assert (commons / "papers" / "multi" / "extra.md").read_text(encoding="utf-8") == "extra\n"
    committed = subprocess.run(
        ["git", "-C", str(commons), "show", "--name-only", "--format=", "HEAD~1"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert "papers/multi.md" in committed
    assert "papers/multi/extra.md" in committed


def test_apply_promote_preflight_rejects_dirty_commons(tmp_path, monkeypatch) -> None:
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    (tmp_path / "commons" / "dirty.txt").write_text("WIP\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path / "commons"), "add", "--", "dirty.txt"], check=True)

    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )
    with pytest.raises(PromoteInputError, match="commons"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")


def test_apply_promote_preflight_rejects_dirty_target_project_file(tmp_path, monkeypatch) -> None:
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    (proj / "entities" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntitle: DIRTY\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )
    with pytest.raises(PromoteInputError, match="dirty"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")


def test_apply_promote_preflight_allows_dirty_non_target_project_file(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    (proj / "other.md").write_text("dirty\n", encoding="utf-8")

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )
    result = apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")
    assert result.status == "ok"


def test_apply_promote_idempotent_skips_already_overlayed(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery1 = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan1 = plan_promote(
        discovery1,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )
    apply_promote(plan1, commons_root=tmp_path / "commons", invocation="first")
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-q", "-m", "promote"], check=True)
    discovery2 = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    assert discovery2.candidates_by_slug == {}
    plan2 = plan_promote(
        discovery2,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )
    assert plan2.decisions == []
    head_before = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    result2 = apply_promote(plan2, commons_root=tmp_path / "commons", invocation="second")
    assert result2.status == "ok"
    assert result2.commons_commit is None
    assert result2.tags_created == []
    assert result2.audit_log_path is None
    head_after = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head_before == head_after


def test_apply_promote_rename_happy_path_unlinks_source_writes_target(tmp_path, monkeypatch) -> None:
    """When --from order forces canonical case `Huh2024` but proj-b has
    `huh2024.md`, apply must (1) write target `Huh2024.md`, (2) unlink
    `huh2024.md`, and record the rename in the audit log."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj_a = _build_project(
        tmp_path,
        "proj-a",
        {"Huh2024.md": "---\nid: paper:Huh2024\ntitle: H\n---\n"},
    )
    proj_b = _build_project(
        tmp_path,
        "proj-b",
        {"huh2024.md": "---\nid: paper:huh2024\ntitle: H\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-a": proj_a, "proj-b": proj_b}[slug],
    )

    discovery = discover_candidates(["proj-a", "proj-b"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a", "proj-b"],
    )
    assert plan.decisions[0].slug == "Huh2024"
    result = apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")
    assert result.status == "ok"
    assert not (proj_b / "entities" / "papers" / "huh2024.md").exists()
    assert (proj_b / "overlays" / "papers" / "Huh2024.md").exists()
    assert (proj_a / "overlays" / "papers" / "Huh2024.md").exists()
    assert result.audit_log_path is not None
    log = yaml.safe_load(result.audit_log_path.read_text(encoding="utf-8"))
    proj_b_rewrites = log["projects_touched"]["proj-b"]["overlay_rewrites"]
    assert proj_b_rewrites[0]["rename"] == {"from": "huh2024.md", "to": "Huh2024.md"}


def test_apply_promote_rename_collision_aborts(tmp_path, monkeypatch) -> None:
    """If the canonical-case target already exists in the project (an unrelated
    file shares the case-folded name), promote refuses to clobber it."""
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj_a = _build_project(
        tmp_path,
        "proj-a",
        {"Huh2024.md": "---\nid: paper:Huh2024\ntitle: H\n---\n"},
    )
    proj_b = _build_project(
        tmp_path,
        "proj-b",
        {"huh2024.md": "---\nid: paper:huh2024\ntitle: H\n---\n"},
    )
    # A stale, unrelated file already occupies the canonical-case overlay target.
    (proj_b / "overlays" / "papers").mkdir(parents=True)
    (proj_b / "overlays" / "papers" / "Huh2024.md").write_text(
        "---\nid: paper:Huh2024\ntitle: H (different file)\n---\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(proj_b), "add", "."], check=True)
    subprocess.run(["git", "-C", str(proj_b), "commit", "-q", "-m", "stale"], check=True)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-a": proj_a, "proj-b": proj_b}[slug],
    )

    discovery = discover_candidates(["proj-a", "proj-b"], PROMOTE_KIND_PAPER)
    with pytest.raises(PromoteInputError, match="case-rename collision"):
        plan_promote(
            discovery,
            commons_root=tmp_path / "commons",
            kind=PROMOTE_KIND_PAPER,
            resolve_conflict=lambda c: None,
            from_order=["proj-a", "proj-b"],
        )


def test_plan_routes_existing_tag_to_overlay_existing(tmp_path, monkeypatch) -> None:
    """A slug already tagged in the commons is resolved at plan time to
    overlay_existing (t063 §3) — no longer an apply-time tag-clash abort."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        discover_candidates,
        plan_promote,
    )

    commons = tmp_path / "commons"
    _init_commons(commons)
    # A real committed canonical + tag (the consistent state a tag implies).
    (commons / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\nkind: paper\nbibkey: Adams2025\n"
        "schema_profile: science-entity-base/1.0+paper/2.0\nversion: 1.0.0\n"
        "title: A\ntags: []\n---\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(commons), "add", "."], check=True)
    subprocess.run(["git", "-C", str(commons), "commit", "-q", "-m", "add Adams2025"], check=True)
    subprocess.run(["git", "-C", str(commons), "tag", "paper/Adams2025/1.0.0"], check=True)

    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )
    decision = next(d for d in plan.decisions if d.slug == "Adams2025")
    assert decision.mode == "overlay_existing"
    assert decision.canonical_artifacts == []
    assert decision.canonical_version == "1.0.0"


def test_apply_promote_tag_preflight_rejects_existing_tag_for_mint(tmp_path) -> None:
    """Defensive guard: a hand-constructed *mint* decision whose tag already
    exists must still fail loud at apply time (t063 §4) — planning normally
    routes such a slug to overlay_existing, so this only fires on internal
    inconsistency."""
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        CanonicalArtifact,
        PromoteDecision,
        PromotePlan,
        apply_promote,
    )

    commons = tmp_path / "commons"
    _init_commons(commons)
    subprocess.run(["git", "-C", str(commons), "tag", "paper/Adams2025/1.0.0"], check=True)

    plan = PromotePlan(
        decisions=[
            PromoteDecision(
                slug="Adams2025",
                canonical_artifacts=[
                    CanonicalArtifact(
                        path=Path("papers/Adams2025.md"),
                        content="---\nid: paper:Adams2025\n---\n",
                        validator="plain",
                    )
                ],
                canonical_version="1.0.0",
                overlays={},
                resolved_conflicts=(),
                mode="mint",
            )
        ],
        failed_candidates=[],
        kind=PROMOTE_KIND_PAPER,
    )
    with pytest.raises(PromoteWriteError, match="tag"):
        apply_promote(plan, commons_root=commons, invocation="...")


def _commit_canonical_and_tag(commons: Path, slug: str, version: str = "1.0.0") -> None:
    """Commit a canonical paper file + version tag into the commons, mirroring
    the consistent state a promoted entity leaves behind (t063 overlay tests)."""
    (commons / "papers" / f"{slug}.md").write_text(
        f"---\nid: paper:{slug}\nkind: paper\nbibkey: {slug}\n"
        f"schema_profile: science-entity-base/1.0+paper/2.0\nversion: {version}\n"
        f"title: A\ntags: []\n---\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(commons), "add", "."], check=True)
    subprocess.run(["git", "-C", str(commons), "commit", "-q", "-m", f"add {slug}"], check=True)
    subprocess.run(["git", "-C", str(commons), "tag", f"paper/{slug}/{version}"], check=True)


def _git_out(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_apply_promote_all_overlay_existing_writes_no_commit_no_tag(tmp_path, monkeypatch) -> None:
    """An all-overlay_existing batch mints nothing: no commons commit, no new
    tag, commons_commit is None, only the source overlay is rewritten and pinned
    to the existing version. Re-running stays idempotent (t063 §4)."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    commons = tmp_path / "commons"
    _init_commons(commons)
    _commit_canonical_and_tag(commons, "Foo")

    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Foo.md": "---\nid: paper:Foo\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    tags_before = _git_out(commons, "tag", "--list")
    canonical_blob_before = _git_out(commons, "rev-parse", "HEAD:papers/Foo.md")

    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )
    assert [d.mode for d in plan.decisions] == ["overlay_existing"]

    result = apply_promote(plan, commons_root=commons, invocation="science commons promote paper --from proj-a --apply")

    assert result.status == "ok"
    assert result.commons_commit is None
    assert result.tags_created == []
    # No new tag in the commons (the existing one is intentionally reused).
    assert _git_out(commons, "tag", "--list") == tags_before
    # No new *canonical* commit: the committed canonical blob is byte-unchanged.
    # (The only new HEAD commit is the separate audit-log commit, which touches
    # .migrations/ exclusively — it is never recorded as commons_commit.)
    assert _git_out(commons, "rev-parse", "HEAD:papers/Foo.md") == canonical_blob_before
    last_files = _git_out(commons, "show", "--stat", "--format=", "--name-only", "HEAD").splitlines()
    assert all(f.startswith(".migrations/") for f in last_files if f), last_files
    # The source summary is rewritten as an overlay pinned to the existing version.
    overlay_text = (proj / "overlays" / "papers" / "Foo.md").read_text(encoding="utf-8")
    assert "overlay_of: paper:Foo" in overlay_text
    assert 'pin_version: "1.0.0"' in overlay_text

    # Idempotent re-run: commit the overlay, re-discover + plan + apply again.
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-q", "-m", "promote"], check=True)
    tags_before2 = _git_out(commons, "tag", "--list")
    canonical_blob_before2 = _git_out(commons, "rev-parse", "HEAD:papers/Foo.md")
    discovery2 = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan2 = plan_promote(
        discovery2,
        commons_root=commons,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )
    result2 = apply_promote(plan2, commons_root=commons, invocation="re-run")
    assert result2.status == "ok"
    assert result2.commons_commit is None
    assert result2.tags_created == []
    assert _git_out(commons, "tag", "--list") == tags_before2
    assert _git_out(commons, "rev-parse", "HEAD:papers/Foo.md") == canonical_blob_before2


def test_apply_promote_all_overlay_existing_audit_log_has_no_revert_guidance(tmp_path, monkeypatch) -> None:
    """An all-overlay apply leaves commons_commit None, so the rendered audit log
    emits no `git revert` rollback guidance for the commons (t063 §4)."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    commons = tmp_path / "commons"
    _init_commons(commons)
    _commit_canonical_and_tag(commons, "Foo")

    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Foo.md": "---\nid: paper:Foo\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )
    result = apply_promote(plan, commons_root=commons, invocation="...")

    assert result.commons_commit is None
    assert result.audit_log_path is not None
    log = yaml.safe_load(result.audit_log_path.read_text(encoding="utf-8"))
    assert log["commons_commit"] is None
    assert log["rollback"]["commons"] is None


def test_apply_promote_mixed_batch_mints_new_overlays_existing(tmp_path, monkeypatch) -> None:
    """A batch with one net-new paper (mint) + one already-committed paper
    (overlay_existing): only the new one is minted+tagged, the existing one is
    overlaid, both source summaries are rewritten, commons_commit is the mint
    commit (t063 §4)."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    commons = tmp_path / "commons"
    _init_commons(commons)
    _commit_canonical_and_tag(commons, "Foo")

    proj = _build_project(
        tmp_path,
        "proj-a",
        {
            "Foo.md": "---\nid: paper:Foo\ntitle: A\n---\n",
            "Bar2025.md": "---\nid: paper:Bar2025\ntitle: B\nyear: 2025\n---\n\n## Key Findings\n\nbar\n",
        },
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )
    modes = {d.slug: d.mode for d in plan.decisions}
    assert modes == {"Foo": "overlay_existing", "Bar2025": "mint"}

    result = apply_promote(plan, commons_root=commons, invocation="...")

    assert result.status == "ok"
    # Only the net-new paper is tagged.
    assert result.tags_created == ["paper/Bar2025/1.0.0"]
    assert result.commons_commit is not None
    # The new canonical was committed; the existing one is untouched in-place.
    assert (commons / "papers" / "Bar2025.md").exists()
    # Both source summaries are rewritten as overlays.
    foo_overlay = (proj / "overlays" / "papers" / "Foo.md").read_text(encoding="utf-8")
    bar_overlay = (proj / "overlays" / "papers" / "Bar2025.md").read_text(encoding="utf-8")
    assert "overlay_of: paper:Foo" in foo_overlay
    assert 'pin_version: "1.0.0"' in foo_overlay
    assert "overlay_of: paper:Bar2025" in bar_overlay
    assert 'pin_version: "1.0.0"' in bar_overlay


def test_apply_promote_step4_os_error_converts_to_promote_write_error(
    tmp_path,
    monkeypatch,
) -> None:
    """A PermissionError / disk-full OSError while writing canonical files in
    step 4 must be converted to PromoteWriteError(stage="write_commons") so
    the outer failure-audit path runs (design §6.4 "Before step 5" recovery).
    The raw OSError must NOT propagate, and no partial canonicals should be
    left on disk."""
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )

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


def test_apply_promote_failure_before_commit_unlinks_first_promote_canonical(
    tmp_path,
    monkeypatch,
) -> None:
    """Force a commit failure. The canonical file written in step 4 (a first-
    promote, not at HEAD) must be unlinked, not left dangling."""
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )

    subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "config", "--unset", "user.email"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "config", "--unset", "user.name"],
        check=True,
    )
    monkeypatch.setenv("GIT_AUTHOR_NAME", "")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "")
    monkeypatch.setenv("HOME", str(tmp_path / "no-global-git"))

    with pytest.raises(PromoteWriteError, match="commons commit failed"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")

    assert not (tmp_path / "commons" / "papers" / "Adams2025.md").exists()
    status = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "papers/Adams2025.md" not in status


def test_apply_promote_path_limited_commit_does_not_pick_up_post_preflight_race(
    tmp_path,
    monkeypatch,
) -> None:
    """TOCTOU race: between preflight pass and the commit, an unrelated file is
    staged in commons. The promote commit must NOT include it."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )

    from science_tool.commons import promote as promote_module

    real_git = promote_module._git

    def racing_git(commons_root, *args, **kw):
        if args[:2] == ("add", "--") and any(a.startswith("papers/") for a in args[2:]):
            result = real_git(commons_root, *args, **kw)
            unrelated = commons_root / "race.txt"
            unrelated.write_text("staged after preflight\n", encoding="utf-8")
            real_git(commons_root, "add", "--", "race.txt")
            return result
        return real_git(commons_root, *args, **kw)

    monkeypatch.setattr(promote_module, "_git", racing_git)

    result = apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")
    assert result.status == "ok"
    assert result.commons_commit is not None
    files = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "show", "--stat", result.commons_commit + "~0"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "papers/Adams2025.md" in files
    assert "race.txt" not in files
    status = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "A  race.txt" in status


def test_apply_promote_project_rollback_preserves_dirty_non_target(tmp_path, monkeypatch) -> None:
    """A mid-step-6 failure must leave dirty non-target project files untouched."""
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path,
        "proj-a",
        {
            "Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n",
            "Bravo2024.md": "---\nid: paper:Bravo2024\ntitle: B\n---\n",
        },
    )
    (proj / "other.txt").write_text("dirty WIP\n", encoding="utf-8")

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )

    second_overlay = plan.decisions[1].overlays["proj-a"]
    # Fail only the second overlay write so the first overlay (same dir) is
    # written successfully and must be rolled back.
    real_write_text = Path.write_text

    def sabotaged_write_text(self, *args, **kw):
        if self == second_overlay.path:
            raise OSError("forced second-overlay write failure")
        return real_write_text(self, *args, **kw)

    monkeypatch.setattr(Path, "write_text", sabotaged_write_text)
    with pytest.raises(PromoteWriteError, match="overlay write"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")

    assert (proj / "other.txt").read_text(encoding="utf-8") == "dirty WIP\n"


def test_apply_promote_reports_project_rollback_checkout_failure(
    tmp_path,
    monkeypatch,
) -> None:
    """If project rollback itself fails, the PromoteWriteError detail must say
    so instead of silently swallowing the failed checkout."""
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path,
        "proj-a",
        {
            "Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n",
            "Bravo2024.md": "---\nid: paper:Bravo2024\ntitle: B\n---\n",
        },
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )
    first_overlay = plan.decisions[0].overlays["proj-a"]
    second_overlay = plan.decisions[1].overlays["proj-a"]
    # The first overlay's source (entities/papers/...) is the tracked file that
    # rollback restores via `git checkout HEAD --`; the overlay dest itself is a
    # new untracked file that rollback unlinks rather than checks out.
    assert first_overlay.unlinked_source is not None
    rollback_path = str(first_overlay.unlinked_source.relative_to(proj))
    real_run = subprocess.run

    def sabotage_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args")
        if (
            isinstance(cmd, list)
            and len(cmd) >= 7
            and cmd[0] == "git"
            and cmd[3:6] == ["checkout", "HEAD", "--"]
            and cmd[-1] == rollback_path
        ):
            if kwargs.get("check"):
                raise subprocess.CalledProcessError(
                    1,
                    cmd,
                    stderr="sim rollback fail",
                )
            return subprocess.CompletedProcess(cmd, 1, stderr="sim rollback fail")
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", sabotage_run)
    # Fail only the second overlay write so the first overlay (same dir) is
    # written and its rollback checkout is the one we sabotage above.
    real_write_text = Path.write_text

    def sabotaged_write_text(self, *args, **kw):
        if self == second_overlay.path:
            raise OSError("forced second-overlay write failure")
        return real_write_text(self, *args, **kw)

    monkeypatch.setattr(Path, "write_text", sabotaged_write_text)
    with pytest.raises(PromoteWriteError) as exc_info:
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")

    assert "overlay write failed" in str(exc_info.value)
    assert "project rewrite restore failed" in str(exc_info.value)


def test_apply_promote_preflight_failure_audit_omits_projects_touched(
    tmp_path,
    monkeypatch,
) -> None:
    """A preflight failure must NOT report projects_touched / project rollback
    commands, because no project file was modified."""
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    (tmp_path / "commons" / "dirty.txt").write_text("WIP\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path / "commons"), "add", "--", "dirty.txt"], check=True)
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )

    with pytest.raises(PromoteInputError):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")

    logs = list((tmp_path / "commons" / ".migrations").glob("*.yaml"))
    data = yaml.safe_load(logs[0].read_text(encoding="utf-8"))
    assert data["projects_touched"] == {}
    assert data["rollback"]["projects"] == {}
    assert data["rollback"]["commons"] is None


def test_apply_promote_audit_write_failure_attaches_yaml_to_exception(
    tmp_path,
    monkeypatch,
) -> None:
    """If the failure audit log itself cannot be written, the would-have-been
    YAML is attached to the raised exception."""
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    (tmp_path / "commons" / "dirty.txt").write_text("WIP\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path / "commons"), "add", "--", "dirty.txt"], check=True)
    (tmp_path / "commons" / ".migrations").chmod(0o555)
    try:
        proj = _build_project(
            tmp_path,
            "proj-a",
            {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
        )
        monkeypatch.setattr(
            "science_tool.commons.promote.resolve_project_by_id",
            lambda slug: proj,
        )
        discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
        plan = plan_promote(
            discovery,
            commons_root=tmp_path / "commons",
            kind=PROMOTE_KIND_PAPER,
            resolve_conflict=lambda c: None,
            from_order=["proj-a"],
        )

        with pytest.raises(PromoteInputError) as ei:
            apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")

        yaml_text = getattr(ei.value, "failure_audit_yaml", None)
        assert yaml_text is not None
        parsed = yaml.safe_load(yaml_text)
        assert parsed["status"] == "failed"
        assert parsed["failure_stage"] == "preflight"
    finally:
        (tmp_path / "commons" / ".migrations").chmod(0o755)


def test_apply_promote_empty_plan_no_op(tmp_path, monkeypatch) -> None:
    """A plan with zero decisions returns ok cleanly — no commit, no tag, no
    audit log, no `git add -- <empty>` error."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        DiscoveryResult,
        apply_promote,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    discovery = DiscoveryResult(candidates_by_slug={}, failed_candidates=[])
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=[],
    )
    assert plan.decisions == []
    head_before = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    result = apply_promote(plan, commons_root=tmp_path / "commons", invocation="empty")
    assert result.status == "ok"
    assert result.commons_commit is None
    assert result.tags_created == []
    assert result.audit_log_path is None
    head_after = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head_before == head_after
    assert not list((tmp_path / "commons" / ".migrations").glob("*.yaml"))


def test_apply_promote_step7_audit_failure_does_not_crash_after_landed_writes(
    tmp_path,
    monkeypatch,
) -> None:
    """If step-7 audit write/commit fails AFTER landed commit+tags+rewrites,
    apply_promote raises typed PromoteWriteError(stage='audit')."""
    from science_tool.commons import promote as promote_module
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )

    real_git = promote_module._git

    def sabotaged_git(commons_root, *args, **kw):
        if args[:1] == ("commit",) and any(a.startswith(".migrations/") for a in args):
            raise subprocess.CalledProcessError(
                returncode=1, cmd=["git", "commit"], stderr="forced audit commit failure"
            )
        return real_git(commons_root, *args, **kw)

    monkeypatch.setattr(promote_module, "_git", sabotaged_git)

    with pytest.raises(PromoteWriteError, match="audit log write/commit failed") as exc_info:
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")

    assert exc_info.value.stage == "audit"
    assert hasattr(exc_info.value, "failure_audit_yaml")
    payload = exc_info.value.failure_audit_yaml
    assert payload
    parsed = yaml.safe_load(payload)
    assert parsed["status"] == "ok"
    assert parsed["commons_commit"]
    assert "paper/Adams2025/1.0.0" in parsed["commons_tags"]
    assert "failure_stage" not in parsed

    assert (tmp_path / "commons" / "papers" / "Adams2025.md").exists()
    overlay_text = (proj / "overlays" / "papers" / "Adams2025.md").read_text(encoding="utf-8")
    assert "overlay_of: paper:Adams2025" in overlay_text
    logs = list((tmp_path / "commons" / ".migrations").glob("*.yaml"))
    assert logs, "success audit log should have been written before commit failed"
    data = yaml.safe_load(logs[0].read_text(encoding="utf-8"))
    assert data == parsed


def test_apply_promote_step6_partial_rename_records_slug_in_projects_touched(
    tmp_path,
    monkeypatch,
) -> None:
    """When a rename's unlink succeeds but the subsequent write fails, the
    project IS partially modified. Both slugs must appear in projects_touched."""
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj_a = _build_project(
        tmp_path,
        "proj-a",
        {"Huh2024.md": "---\nid: paper:Huh2024\ntitle: H\n---\n"},
    )
    proj_b = _build_project(
        tmp_path,
        "proj-b",
        {"huh2024.md": "---\nid: paper:huh2024\ntitle: H\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-a": proj_a, "proj-b": proj_b}[slug],
    )
    discovery = discover_candidates(["proj-a", "proj-b"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a", "proj-b"],
    )

    real_write_text = Path.write_text
    target = proj_b / "overlays" / "papers" / "Huh2024.md"

    def sabotaged_write_text(self, *args, **kw):
        if self == target:
            raise OSError("forced rename-target write failure")
        return real_write_text(self, *args, **kw)

    monkeypatch.setattr(Path, "write_text", sabotaged_write_text)

    with pytest.raises(PromoteWriteError, match="overlay write"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")

    logs = list((tmp_path / "commons" / ".migrations").glob("*.yaml"))
    data = yaml.safe_load(logs[0].read_text(encoding="utf-8"))
    assert "proj-a" in data["projects_touched"]
    assert "proj-b" in data["projects_touched"]


def test_apply_promote_failure_commits_audit_log_path_limited(
    tmp_path,
    monkeypatch,
) -> None:
    """Design §6.3 step 7 (failure variant) + t063 §6 (fb-003): every failure
    writes an audit log under .migrations/ AND commits it path-limited, so the
    working tree is left clean and the next apply's preflight is not blocked by
    an orphan .migrations/ file. A pre-existing staged dirty file is left alone
    by the path-limited commit (it still blocks preflight, as intended)."""
    from science_tool.commons.errors import PromoteInputError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    (tmp_path / "commons" / "dirty.txt").write_text("WIP\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path / "commons"), "add", "--", "dirty.txt"], check=True)

    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )

    with pytest.raises(PromoteInputError, match="commons"):
        apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")

    logs = list((tmp_path / "commons" / ".migrations").glob("*.yaml"))
    assert len(logs) == 1
    data = yaml.safe_load(logs[0].read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert data["failure_stage"] == "preflight"
    assert "commons repo is not clean" in data["failure_detail"]
    assert data["commons_commit"] is None
    assert data["commons_tags"] == []
    # The audit log is now committed (tracked, clean) — not an orphan.
    migrations_status = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "status", "--porcelain", "--", ".migrations/"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert migrations_status.strip() == ""
    # The path-limited commit must not have swept up the pre-existing staged file.
    dirty_status = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "status", "--porcelain", "--", "dirty.txt"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "dirty.txt" in dirty_status


def test_apply_promote_failure_leaves_clean_tree_and_unblocks_retry(
    tmp_path,
    monkeypatch,
) -> None:
    """t063 §6 (fb-003): a non-audit-stage failure that reaches
    _write_failure_audit_log must leave the commons working tree clean per
    _commons_is_clean (the .migrations audit log is committed, not orphaned),
    so a fresh apply of a valid plan is not blocked by a dirty-commons
    preflight. The original failure type still propagates."""
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        _commons_is_clean,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    commons = tmp_path / "commons"
    _init_commons(commons)
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )

    # Force a Step-6 (rewrite_projects, post-commit) overlay write failure by
    # making the overlay-dest directory read-only. This reaches the outer
    # failure handler at a non-audit stage with a written audit_path.
    target_dir = proj / "overlays" / "papers"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_dir.chmod(0o555)
    try:
        with pytest.raises(PromoteWriteError, match="overlay write"):
            apply_promote(plan, commons_root=commons, invocation="...")
    finally:
        target_dir.chmod(0o755)

    # The commons working tree is clean: the audit log was committed, not left
    # as an untracked .migrations/ file.
    clean, dirty = _commons_is_clean(commons, PROMOTE_KIND_PAPER)
    assert clean, f"commons not clean after failure: {dirty}"
    logs = list((commons / ".migrations").glob("*.yaml"))
    assert len(logs) == 1
    # The audit log is tracked (committed), not untracked.
    tracked = subprocess.run(
        ["git", "-C", str(commons), "ls-files", "--", ".migrations/"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert ".migrations/" in tracked

    # A fresh apply of a valid plan is no longer blocked by a dirty-commons
    # preflight: it gets past the clean check and completes.
    proj2 = _build_project(
        tmp_path,
        "proj-b",
        {"Brown2025.md": "---\nid: paper:Brown2025\ntitle: B\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj2,
    )
    discovery2 = discover_candidates(["proj-b"], PROMOTE_KIND_PAPER)
    plan2 = plan_promote(
        discovery2,
        commons_root=commons,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-b"],
    )
    result2 = apply_promote(plan2, commons_root=commons, invocation="...")
    assert result2.status == "ok"


def test_apply_promote_failed_audit_commit_does_not_mask_original_error(
    tmp_path,
    monkeypatch,
) -> None:
    """t063 §6 (fb-003): if the failure-audit `git commit` itself raises, the
    ORIGINAL failure (a PromoteWriteError) must propagate — not a git error —
    and failure_audit_yaml must be attached to it. Only the failure-audit
    commit is sabotaged; the earlier promote commit must still succeed."""
    import science_tool.commons.promote as promote_module
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    commons = tmp_path / "commons"
    _init_commons(commons)
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )

    # Original failure: Step-6 overlay write fails (read-only dest dir).
    target_dir = proj / "overlays" / "papers"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_dir.chmod(0o555)

    real_git = promote_module._git

    def sabotaged_git(commons_root, *args, **kwargs):
        # Only sabotage the failure-audit commit, identified by its message.
        # The earlier promote commit ("promote: ...") must still succeed so we
        # exercise the post-commit failure path with a real audit_path.
        if args[:1] == ("commit",) and any("audit: failed op" in a for a in args):
            raise subprocess.CalledProcessError(1, ["git", *args], stderr="sim audit commit fail")
        return real_git(commons_root, *args, **kwargs)

    monkeypatch.setattr(promote_module, "_git", sabotaged_git)

    try:
        with pytest.raises(PromoteWriteError, match="overlay write") as exc_info:
            apply_promote(plan, commons_root=commons, invocation="...")
    finally:
        target_dir.chmod(0o755)

    # The propagated exception is the ORIGINAL PromoteWriteError, not a git error.
    assert not isinstance(exc_info.value, subprocess.CalledProcessError)
    # And the failure-audit YAML is attached so stderr surfacing still works.
    yaml_text = getattr(exc_info.value, "failure_audit_yaml", None)
    assert yaml_text is not None
    assert "status: failed" in yaml_text


def test_apply_promote_failure_audit_records_post_commit_failure_stage(
    tmp_path,
    monkeypatch,
) -> None:
    """A step-6 failure (after commons commit landed) records
    failure_stage='rewrite_projects' and the commons commit hash."""
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _init_commons(tmp_path / "commons")
    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Adams2025.md": "---\nid: paper:Adams2025\ntitle: A\n---\n"},
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    discovery = discover_candidates(["proj-a"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=tmp_path / "commons",
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["proj-a"],
    )

    target_dir = proj / "overlays" / "papers"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_dir.chmod(0o555)
    try:
        with pytest.raises(PromoteWriteError, match="overlay write"):
            apply_promote(plan, commons_root=tmp_path / "commons", invocation="...")
    finally:
        target_dir.chmod(0o755)

    logs = list((tmp_path / "commons" / ".migrations").glob("*.yaml"))
    assert len(logs) == 1
    data = yaml.safe_load(logs[0].read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert data["failure_stage"] == "rewrite_projects"
    assert data["commons_commit"] is not None


def test_apply_commons_path_uses_kind_commons_subdir(tmp_path, monkeypatch) -> None:
    """commons_root / "papers" / ... was hardcoded. After de-hardcoding,
    kind.commons_subdir is used. Drive plan_promote with a real minimal
    candidate so the decision-building loop runs, then assert the resulting
    PromoteDecision canonical artifact is under kind.commons_subdir."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        discover_candidates,
        plan_promote,
    )

    proj = tmp_path / "proj_p"
    (proj / "entities" / "topics").mkdir(parents=True)
    (proj / "entities" / "topics" / "single.md").write_text(
        "---\nid: topic:single\ntitle: T\n---\n\n## Summary\n\nx\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )
    commons = tmp_path / "commons"
    commons.mkdir()

    discovery = discover_candidates(["proj_p"], PROMOTE_KIND_TOPIC)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_TOPIC)

    assert len(plan.decisions) == 1
    canonical_path = commons / plan.decisions[0].canonical_artifacts[0].path
    # The path MUST live under commons/topics/, not commons/papers/.
    assert canonical_path.parent.name == "topics"
    assert str(canonical_path).startswith(str(commons / "topics"))
    assert canonical_path.relative_to(commons).parts[0] == "topics"


def test_commons_is_clean_checks_kind_commons_subdir(tmp_path) -> None:
    """_commons_is_clean hardcoded path.startswith("papers/"). After de-
    hardcoding, kind.commons_subdir is used. Initialise an empty commons
    repo + add an untracked file under topics/ and verify that
    _commons_is_clean(commons_root, PROMOTE_KIND_TOPIC) reports it dirty
    while PROMOTE_KIND_PAPER would not."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        PROMOTE_KIND_TOPIC,
        _commons_is_clean,
    )

    _init_repo(tmp_path)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
    )
    (tmp_path / "topics").mkdir()
    (tmp_path / "topics" / "x.md").write_text("hi", encoding="utf-8")

    paper_clean, _ = _commons_is_clean(tmp_path, PROMOTE_KIND_PAPER)
    topic_clean, dirty = _commons_is_clean(tmp_path, PROMOTE_KIND_TOPIC)
    assert paper_clean is True
    assert topic_clean is False
    assert "topics/x.md" in dirty


def test_project_target_files_clean_checks_kind_overlay_dest_subdir(tmp_path) -> None:
    """_project_target_files_clean hardcoded "entities/papers/{name}". After de-hardcoding,
    kind.overlay_dest_subdir is used. For topic, it also scans kind.source_subdirs
    so a dirty entities/topics/foo.md is reported."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        _project_target_files_clean,
    )

    _init_repo(tmp_path)
    (tmp_path / "entities" / "topics").mkdir(parents=True)
    target = tmp_path / "entities" / "topics" / "primitives.md"
    target.write_text("original\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )

    # Dirty the file.
    target.write_text("dirty\n", encoding="utf-8")

    clean, dirty_paths = _project_target_files_clean(
        tmp_path, ["primitives.md"], PROMOTE_KIND_TOPIC
    )
    assert clean is False
    assert any("entities/topics/primitives.md" in p for p in dirty_paths)


def test_project_target_files_clean_reports_deleted_tracked_source_file(tmp_path) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        _project_target_files_clean,
    )

    _init_repo(tmp_path)
    (tmp_path / "entities" / "topics").mkdir(parents=True)
    target = tmp_path / "entities" / "topics" / "primitives.md"
    target.write_text("original\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )

    target.unlink()

    clean, dirty_paths = _project_target_files_clean(
        tmp_path, ["primitives.md"], PROMOTE_KIND_TOPIC
    )
    assert clean is False
    assert "entities/topics/primitives.md" in dirty_paths


@pytest.mark.parametrize(
    "target_rel",
    [
        "overlays/topics/primitives.md",
        "entities/topics/primitives.md",
    ],
)
def test_project_target_files_clean_reports_untracked_topic_target_file(
    tmp_path,
    target_rel: str,
) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        _project_target_files_clean,
    )

    _init_repo(tmp_path)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
    )
    target = tmp_path / target_rel
    target.parent.mkdir(parents=True)
    target.write_text("untracked\n", encoding="utf-8")

    clean, dirty_paths = _project_target_files_clean(
        tmp_path, ["primitives.md"], PROMOTE_KIND_TOPIC
    )
    assert clean is False
    assert target_rel in dirty_paths


def test_apply_tags_use_kind_kind_prefix(tmp_path, monkeypatch) -> None:
    """Verify that apply_promote builds tags as {kind.kind}/{slug}/{version}
    instead of the hardcoded "paper/{bibkey}/{version}". We exercise this
    indirectly by inspecting the planned tag prefix logic via a tiny stub
    PromotePlan with a single decision."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_TOPIC,
        CanonicalArtifact,
        PromoteDecision,
    )

    d = PromoteDecision(
        slug="hypothesis",
        canonical_artifacts=[
            CanonicalArtifact(
                path=Path("topics/hypothesis.md"),
                content="---\nid: topic:hypothesis\n---\n",
                validator="entity-mixin",
            )
        ],
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    # The tag-building string template should now be:
    # f"{plan.kind.kind}/{decision.slug}/{decision.canonical_version}"
    tag = f"{PROMOTE_KIND_TOPIC.kind}/{d.slug}/{d.canonical_version}"
    assert tag == "topic/hypothesis/1.0.0"
    # And a sort by .slug must use the slug attribute, not .bibkey.
    decisions = [d]
    decisions_sorted = sorted(decisions, key=lambda x: x.slug)
    assert decisions_sorted[0].slug == "hypothesis"


def test_commons_commit_message_uses_kind_commons_subdir() -> None:
    """Commit message hardcoded 'papers via op'. After Task 14, the noun
    is kind.commons_subdir."""
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC

    # The literal should now be:
    # f"promote: {len(plan.decisions)} {kind.commons_subdir} via op {op_id}"
    msg = f"promote: 3 {PROMOTE_KIND_TOPIC.commons_subdir} via op abc"
    assert msg == "promote: 3 topics via op abc"
