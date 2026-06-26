from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, NoReturn

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


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    proj = tmp_path / "proj-dataset"
    shutil.copytree(FIXTURES / "proj-dataset", proj)
    _init_repo(proj)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(proj), "commit", "-q", "-m", "init"],
        check=True,
        capture_output=True,
    )

    commons = tmp_path / "commons"
    commons.mkdir()
    (commons / ".migrations").mkdir()
    (commons / "datasets").mkdir()
    _init_repo(commons)
    subprocess.run(
        ["git", "-C", str(commons), "commit", "--allow-empty", "-q", "-m", "init"],
        check=True,
        capture_output=True,
    )

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SCIENCE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-dataset": proj}[slug],
    )
    return proj, commons


def _git_stdout(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit_all(root: Path, message: str = "update") -> None:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-q", "-m", message],
        check=True,
        capture_output=True,
    )


def _replace_single_dataset(proj: Path, slug: str, frontmatter: str) -> None:
    dataset_dir = proj / "entities" / "datasets"
    for path in dataset_dir.glob("*.md"):
        path.unlink()
    (dataset_dir / f"{slug}.md").write_text(
        f"---\n{frontmatter}---\n# {slug}\n",
        encoding="utf-8",
    )


def _snapshot_state(commons: Path, data_yaml: Path) -> dict[str, Any]:
    """Capture pre-apply state for byte-identity rollback assertions."""
    artifact_paths = [
        commons / "datasets" / "fixture-ds" / "entity.md",
        commons / "datasets" / "fixture-ds" / "datapackage.yaml",
        commons / "datasets" / "fixture-ds" / "recipe" / "README.md",
    ]
    return {
        "head": _git_stdout(commons, "rev-parse", "HEAD"),
        "tags": _git_stdout(commons, "tag", "-l"),
        "artifacts": {
            str(path.relative_to(commons)): path.read_bytes() if path.is_file() else None
            for path in artifact_paths
        },
        "data_yaml": data_yaml.read_bytes() if data_yaml.is_file() else None,
    }


def _assert_head_unchanged_or_audit_commit(commons: Path, before_head: str) -> None:
    """HEAD after a failed apply is either unchanged (audit log unwritable / git
    broken) or exactly one commit ahead — the failure-audit log commit the outer
    handler now makes path-limited so the working tree is left clean and the next
    apply's preflight is not blocked (t063 fb-003). In the advanced case the new
    commit must be the audit commit and the working tree must be clean."""
    after_head = _git_stdout(commons, "rev-parse", "HEAD")
    if after_head == before_head:
        return
    parent = _git_stdout(commons, "rev-parse", "HEAD~1")
    assert parent == before_head, "HEAD advanced by more than the audit commit"
    subject = _git_stdout(commons, "log", "-1", "--format=%s")
    assert subject.startswith("audit: failed op"), f"unexpected commit on rollback: {subject}"
    porcelain = _git_stdout(commons, "status", "--porcelain")
    assert porcelain == "", f"working tree not clean after rollback: {porcelain}"


def _assert_rolled_back(commons: Path, data_yaml: Path, before: dict[str, Any]) -> None:
    after = _snapshot_state(commons, data_yaml)
    # The dataset operation itself must be fully rolled back: artifacts, tags,
    # and the data.yaml override are byte-identical to the pre-apply state.
    for field in ("tags", "artifacts", "data_yaml"):
        assert after[field] == before[field], f"{field} not rolled back"
    _assert_head_unchanged_or_audit_commit(commons, before["head"])


def test_dataset_apply_writes_three_artifacts_commit_tag_override_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj, commons = _setup(tmp_path, monkeypatch)

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_DATASET,
        from_order=["proj-dataset"],
    )
    result = apply_promote(
        plan,
        commons_root=commons,
        invocation="science commons promote dataset --from proj-dataset --apply",
    )

    assert (commons / "datasets" / "fixture-ds" / "entity.md").is_file()
    assert (commons / "datasets" / "fixture-ds" / "datapackage.yaml").is_file()
    assert (commons / "datasets" / "fixture-ds" / "recipe" / "README.md").is_file()
    assert result.commons_commit is not None
    assert "dataset/fixture-ds/1.0.0" in result.tags_created

    config_dir = tmp_path / ".config" / "science"
    data_yaml = config_dir / "data.yaml"
    assert yaml.safe_load(data_yaml.read_text(encoding="utf-8")) == {
        "fixture-ds": str(proj / "data" / "fixture-ds")
    }
    backup_markers = sorted(config_dir.glob("data.yaml.bak.*"))
    assert len(backup_markers) == 1
    assert backup_markers[0].name.endswith(".absent")

    overlay = proj / "overlays" / "datasets" / "fixture-ds.md"
    overlay_text = overlay.read_text(encoding="utf-8")
    assert "overlay_of: dataset:fixture-ds" in overlay_text
    assert "pin_version" in overlay_text


def test_reference_dataset_promotes_without_datapackage_or_data_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj, commons = _setup(tmp_path, monkeypatch)
    _replace_single_dataset(
        proj,
        "catalog-ref",
        (
            "id: dataset:catalog-ref\n"
            "type: dataset\n"
            "title: Catalog Reference\n"
            "dataset_class: reference\n"
            "origin: external\n"
            "tier: track\n"
            "license: unknown\n"
            "source_refs: [paper:source]\n"
            "access:\n"
            "  level: public\n"
            "  verified: true\n"
            "  verification_method: landing-confirmed\n"
            "  source_url: https://example.org/catalog\n"
        ),
    )
    _commit_all(proj, "reference dataset")

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert discovery.failed_candidates == []
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)

    [decision] = plan.decisions
    assert [artifact.path.as_posix() for artifact in decision.canonical_artifacts] == [
        "datasets/catalog-ref/entity.md"
    ]

    result = apply_promote(plan, commons_root=commons, invocation="test")

    canonical = commons / "datasets" / "catalog-ref" / "entity.md"
    assert canonical.is_file()
    text = canonical.read_text(encoding="utf-8")
    assert "dataset_class: reference" in text
    assert "datapackage:" not in text
    assert not (commons / "datasets" / "catalog-ref" / "datapackage.yaml").exists()
    assert result.side_channel_results["catalog-ref"].artifact_paths == []
    assert not (tmp_path / ".config" / "science" / "data.yaml").exists()


def test_pointer_dataset_promotes_as_metadata_stub_with_runtime_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        discover_candidates,
        plan_promote,
    )

    proj, commons = _setup(tmp_path, monkeypatch)
    _replace_single_dataset(
        proj,
        "pointer-only",
        (
            "id: dataset:pointer-only\n"
            "type: dataset\n"
            "title: Pointer Only\n"
            "dataset_class: pointer\n"
            "origin: external\n"
            "tier: track\n"
            "license: unknown\n"
            "source_refs: [paper:source]\n"
            "access:\n"
            "  level: public\n"
            "  verified: true\n"
            "  verification_method: metadata-confirmed\n"
            "  source_url: https://example.org/record\n"
        ),
    )

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert discovery.failed_candidates == []
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)

    [decision] = plan.decisions
    [artifact] = decision.canonical_artifacts
    assert artifact.path.as_posix() == "datasets/pointer-only/entity.md"
    assert "dataset_class: pointer" in artifact.content
    assert "runtime_state: pointer-only" in artifact.content
    assert "datapackage:" not in artifact.content


def test_dataset_apply_audit_log_records_extras(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _proj, commons = _setup(tmp_path, monkeypatch)

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_DATASET,
        from_order=["proj-dataset"],
    )
    result = apply_promote(
        plan,
        commons_root=commons,
        invocation="science commons promote dataset --from proj-dataset --apply",
    )

    assert result.audit_log_path is not None
    log = yaml.safe_load(result.audit_log_path.read_text(encoding="utf-8"))
    [decision] = [entry for entry in log["decisions"] if entry["slug"] == "fixture-ds"]

    r1 = decision["per_resource_hashes"]["r1"]
    assert r1["hash"].startswith("sha256:")
    assert r1["bytes"] == 12
    assert decision["recipe_stubbed"] is True
    assert "ontologies" in decision["dropped_fields"]
    assert decision["override_file"].endswith("data.yaml")
    op_id = log["op_id"]
    assert (
        decision["override_backup"].endswith(f"data.yaml.bak.{op_id}")
        or decision["override_backup"].endswith(f"data.yaml.bak.{op_id}.absent")
    )


def test_dataset_apply_audit_log_tolerates_malformed_optional_extras(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj, commons = _setup(tmp_path, monkeypatch)
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_DATASET,
        from_order=["proj-dataset"],
    )
    plan = replace(
        plan,
        dataset_audit_extras={
            "fixture-ds": {
                "override_path": str(proj / "data" / "fixture-ds"),
                "per_resource": {"r1": None, "r2": ("sha256:x", object())},
                "dropped_fields": "not-a-list",
                "recipe_stubbed": object(),
            }
        },
    )

    result = apply_promote(
        plan,
        commons_root=commons,
        invocation="science commons promote dataset --from proj-dataset --apply",
    )

    assert result.audit_log_path is not None
    log = yaml.safe_load(result.audit_log_path.read_text(encoding="utf-8"))
    [decision] = [entry for entry in log["decisions"] if entry["slug"] == "fixture-ds"]
    assert decision["per_resource_hashes"] == {}
    assert decision["recipe_stubbed"] is False
    assert decision["dropped_fields"] == []


def test_rollback_overlay_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj, commons = _setup(tmp_path, monkeypatch)
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    before = _snapshot_state(commons, data_yaml)

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_DATASET,
        from_order=["proj-dataset"],
    )
    target_overlay = proj / "overlays" / "datasets" / "fixture-ds.md"
    real_write_text = Path.write_text

    def sabotage(self: Path, *args: Any, **kwargs: Any) -> int:
        if self == target_overlay:
            raise OSError("sim overlay fail")
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", sabotage)

    with pytest.raises(PromoteWriteError, match="overlay write failed"):
        apply_promote(
            plan,
            commons_root=commons,
            invocation="science commons promote dataset --from proj-dataset --apply",
        )

    _assert_rolled_back(commons, data_yaml, before)
    assert not list((tmp_path / ".config" / "science").glob("data.yaml.bak.*"))
    assert not target_overlay.exists()
    logs = list((commons / ".migrations").glob("*.yaml"))
    assert len(logs) == 1
    log = yaml.safe_load(logs[0].read_text(encoding="utf-8"))
    [decision] = [entry for entry in log["decisions"] if entry["slug"] == "fixture-ds"]
    assert decision["override_file"].endswith("data.yaml")
    assert decision["override_backup"].endswith(f"data.yaml.bak.{log['op_id']}.absent")


def test_rollback_artifact_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _proj, commons = _setup(tmp_path, monkeypatch)
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    before = _snapshot_state(commons, data_yaml)
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    target = commons / "datasets" / "fixture-ds" / "datapackage.yaml"
    real_write_text = Path.write_text

    def sabotage(self: Path, *args: Any, **kwargs: Any) -> int:
        if self == target:
            raise OSError("sim artifact write fail")
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", sabotage)

    with pytest.raises(PromoteWriteError, match="write_commons|canonical write"):
        apply_promote(plan, commons_root=commons, invocation="test")

    _assert_rolled_back(commons, data_yaml, before)


def test_rollback_commit_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        _git,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _proj, commons = _setup(tmp_path, monkeypatch)
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    before = _snapshot_state(commons, data_yaml)
    real_git = _git

    def sabotage(commons_root: Path, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:1] == ("commit",):
            raise subprocess.CalledProcessError(1, args, stderr=b"sim commit fail")
        return real_git(commons_root, *args, **kwargs)

    monkeypatch.setattr("science_tool.commons.promote._git", sabotage)
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)

    with pytest.raises(PromoteWriteError, match="commit"):
        apply_promote(plan, commons_root=commons, invocation="test")

    _assert_rolled_back(commons, data_yaml, before)


def test_rollback_tag_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        _git,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _proj, commons = _setup(tmp_path, monkeypatch)
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    before = _snapshot_state(commons, data_yaml)
    real_git = _git

    def sabotage(commons_root: Path, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:1] == ("tag",) and len(args) > 1 and "dataset/" in args[1]:
            raise subprocess.CalledProcessError(1, args, stderr=b"sim tag fail")
        return real_git(commons_root, *args, **kwargs)

    monkeypatch.setattr("science_tool.commons.promote._git", sabotage)
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)

    with pytest.raises(PromoteWriteError, match="tag"):
        apply_promote(plan, commons_root=commons, invocation="test")

    _assert_rolled_back(commons, data_yaml, before)


def test_rollback_override_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _proj, commons = _setup(tmp_path, monkeypatch)
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    before = _snapshot_state(commons, data_yaml)

    def sabotage(**kwargs: Any) -> NoReturn:
        raise OSError("sim override fail")

    monkeypatch.setattr("science_tool.commons.config._upsert_data_override", sabotage)
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)

    with pytest.raises(PromoteWriteError, match="side.channel|override"):
        apply_promote(plan, commons_root=commons, invocation="test")

    _assert_rolled_back(commons, data_yaml, before)


def test_apply_promote_rechecks_stale_dataset_override_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _proj, commons = _setup(tmp_path, monkeypatch)
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_DATASET,
        from_order=["proj-dataset"],
    )

    data_yaml.parent.mkdir(parents=True, exist_ok=True)
    data_yaml.write_text("fixture-ds: /conflicting/path\n", encoding="utf-8")
    before = _snapshot_state(commons, data_yaml)

    with pytest.raises(PromoteWriteError, match="side-channel.*override conflicts") as exc_info:
        apply_promote(
            plan,
            commons_root=commons,
            invocation="science commons promote dataset --from proj-dataset --apply",
        )

    assert exc_info.value.stage == "side_channel"
    _assert_rolled_back(commons, data_yaml, before)
    status = _git_stdout(commons, "status", "--porcelain")
    assert "datasets/fixture-ds" not in status


def test_audit_failure_leaves_migration_landed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _proj, commons = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "science_tool.commons.promote._write_audit_log",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("sim audit fail")),
    )
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)

    with pytest.raises(PromoteWriteError, match="audit") as exc_info:
        apply_promote(plan, commons_root=commons, invocation="test")

    assert (commons / "datasets" / "fixture-ds" / "entity.md").is_file()
    assert "dataset/fixture-ds/1.0.0" in _git_stdout(commons, "tag", "-l")
    assert hasattr(exc_info.value, "failure_audit_yaml")
    payload = exc_info.value.failure_audit_yaml
    assert payload

    parsed = yaml.safe_load(payload)
    assert parsed["status"] == "ok"
    assert parsed["op_id"]
    assert parsed["commons_commit"]
    assert "dataset/fixture-ds/1.0.0" in parsed["commons_tags"]
    assert "failure_stage" not in parsed

    migrations = commons / ".migrations"
    migrations.mkdir(exist_ok=True)
    target = migrations / f"manual-{parsed['op_id']}.yaml"
    target.write_text(payload, encoding="utf-8")
    assert yaml.safe_load(target.read_text(encoding="utf-8")) == parsed


def test_audit_failure_commit_leaves_migration_landed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        _git,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _proj, commons = _setup(tmp_path, monkeypatch)
    real_git = _git

    def sabotage(commons_root: Path, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:1] == ("commit",) and any(arg.startswith(".migrations/") for arg in args):
            raise subprocess.CalledProcessError(1, args, stderr=b"sim audit commit fail")
        return real_git(commons_root, *args, **kwargs)

    monkeypatch.setattr("science_tool.commons.promote._git", sabotage)
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)

    with pytest.raises(PromoteWriteError, match="audit") as exc_info:
        apply_promote(plan, commons_root=commons, invocation="test")

    assert exc_info.value.stage == "audit"
    assert (commons / "datasets" / "fixture-ds" / "entity.md").is_file()
    assert "dataset/fixture-ds/1.0.0" in _git_stdout(commons, "tag", "-l")
    assert hasattr(exc_info.value, "failure_audit_yaml")
    payload = exc_info.value.failure_audit_yaml
    assert payload

    parsed = yaml.safe_load(payload)
    assert parsed["status"] == "ok"
    assert parsed["op_id"]
    assert parsed["commons_commit"]
    assert "dataset/fixture-ds/1.0.0" in parsed["commons_tags"]
    assert "failure_stage" not in parsed


def test_audit_failure_git_oserror_leaves_migration_landed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        _git,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _proj, commons = _setup(tmp_path, monkeypatch)
    real_git = _git

    def sabotage(commons_root: Path, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:1] == ("add",) and any(arg.startswith(".migrations/") for arg in args):
            raise OSError("sim audit git add fail")
        return real_git(commons_root, *args, **kwargs)

    monkeypatch.setattr("science_tool.commons.promote._git", sabotage)
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)

    with pytest.raises(PromoteWriteError, match="audit") as exc_info:
        apply_promote(plan, commons_root=commons, invocation="test")

    assert exc_info.value.stage == "audit"
    assert (commons / "datasets" / "fixture-ds" / "entity.md").is_file()
    assert "dataset/fixture-ds/1.0.0" in _git_stdout(commons, "tag", "-l")
    assert hasattr(exc_info.value, "failure_audit_yaml")
    payload = exc_info.value.failure_audit_yaml
    assert payload

    parsed = yaml.safe_load(payload)
    assert parsed["status"] == "ok"
    assert parsed["commons_commit"]
    assert "dataset/fixture-ds/1.0.0" in parsed["commons_tags"]
    assert "failure_stage" not in parsed


def test_dataset_apply_side_channel_failure_unstages_commons_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        SideChannelContext,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    proj, commons = _setup(tmp_path, monkeypatch)
    before_head = _git_stdout(commons, "rev-parse", "HEAD")
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_DATASET,
        from_order=["proj-dataset"],
    )

    def fail_side_channel(ctx: SideChannelContext) -> NoReturn:
        raise OSError(f"sim side-channel fail for {ctx.decision.slug}")

    plan = replace(plan, kind=replace(plan.kind, side_channel_apply=fail_side_channel))

    with pytest.raises(PromoteWriteError, match="side-channel apply failed"):
        apply_promote(
            plan,
            commons_root=commons,
            invocation="science commons promote dataset --from proj-dataset --apply",
        )

    assert not data_yaml.exists()
    _assert_head_unchanged_or_audit_commit(commons, before_head)
    assert _git_stdout(commons, "tag", "-l") == ""
    status = _git_stdout(commons, "status", "--porcelain")
    assert "datasets/fixture-ds" not in status


def test_dataset_apply_side_channel_candidate_error_rolls_back_commons(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from science_tool.commons.errors import PromoteWriteError
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    _proj, commons = _setup(tmp_path, monkeypatch)
    before_head = _git_stdout(commons, "rev-parse", "HEAD")
    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_DATASET,
        from_order=["proj-dataset"],
    )
    plan = replace(
        plan,
        dataset_audit_extras={"fixture-ds": {"override_path": None}},
    )

    with pytest.raises(PromoteWriteError, match="side-channel apply failed"):
        apply_promote(
            plan,
            commons_root=commons,
            invocation="science commons promote dataset --from proj-dataset --apply",
        )

    _assert_head_unchanged_or_audit_commit(commons, before_head)
    assert _git_stdout(commons, "tag", "-l") == ""
    status = _git_stdout(commons, "status", "--porcelain")
    assert "datasets/fixture-ds" not in status
