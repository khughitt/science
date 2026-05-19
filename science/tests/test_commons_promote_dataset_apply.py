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

    overlay = proj / "doc" / "datasets" / "fixture-ds.md"
    overlay_text = overlay.read_text(encoding="utf-8")
    assert "overlay_of: dataset:fixture-ds" in overlay_text
    assert "pin_version" in overlay_text
