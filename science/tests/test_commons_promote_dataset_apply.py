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

    overlay = proj / "doc" / "datasets" / "data-fixture-ds.md"
    overlay_text = overlay.read_text(encoding="utf-8")
    assert "overlay_of: dataset:fixture-ds" in overlay_text
    assert "pin_version" in overlay_text


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


def test_dataset_apply_overlay_failure_restores_side_channel(
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
    before_head = _git_stdout(commons, "rev-parse", "HEAD")
    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    assert not data_yaml.exists()

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_DATASET,
        from_order=["proj-dataset"],
    )
    target_overlay = proj / "doc" / "datasets" / "data-fixture-ds.md"
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

    assert not data_yaml.exists()
    assert not list((tmp_path / ".config" / "science").glob("data.yaml.bak.*"))
    assert _git_stdout(commons, "rev-parse", "HEAD") != before_head
    assert _git_stdout(commons, "tag", "-l") == "dataset/fixture-ds/1.0.0"
    logs = list((commons / ".migrations").glob("*.yaml"))
    assert len(logs) == 1
    log = yaml.safe_load(logs[0].read_text(encoding="utf-8"))
    [decision] = [entry for entry in log["decisions"] if entry["slug"] == "fixture-ds"]
    assert decision["override_file"].endswith("data.yaml")
    assert decision["override_backup"].endswith(f"data.yaml.bak.{log['op_id']}.absent")


def test_dataset_apply_side_channel_failure_unstages_commons_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from science_tool.commons.errors import PromoteWriteError
    from dataclasses import replace

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
    assert _git_stdout(commons, "rev-parse", "HEAD") == before_head
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

    assert _git_stdout(commons, "rev-parse", "HEAD") == before_head
    assert _git_stdout(commons, "tag", "-l") == ""
    status = _git_stdout(commons, "status", "--porcelain")
    assert "datasets/fixture-ds" not in status
