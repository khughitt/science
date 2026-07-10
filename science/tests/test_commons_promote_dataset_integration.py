"""End-to-end integration test for `science commons promote dataset`.

Drives discover -> plan -> apply over a synthetic project under tmp_path with
XDG_CONFIG_HOME sandboxed. Asserts the full pilot surface.
"""

import shutil
import subprocess
from pathlib import Path

import yaml as pyyaml


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


def test_promote_dataset_end_to_end(tmp_path, monkeypatch):
    src = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
    proj = tmp_path / "proj-dataset"
    shutil.copytree(src, proj)
    _init_repo(proj)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(proj), "commit", "-q", "-m", "init"],
        check=True,
    )

    commons = tmp_path / "commons"
    commons.mkdir()
    _init_repo(commons)
    (commons / "datasets").mkdir()
    (commons / ".migrations").mkdir()
    (commons / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "-C", str(commons), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(commons), "commit", "-q", "-m", "init"],
        check=True,
    )

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SCIENCE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: {"proj-dataset": proj}[slug],
    )

    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        apply_promote,
        discover_candidates,
        plan_promote,
    )

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)
    assert discovery.failed_candidates == []
    plan = plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_DATASET)
    apply_promote(plan, commons_root=commons, invocation="integration")

    assert (commons / "datasets/fixture-ds/entity.md").is_file()
    dp = (commons / "datasets/fixture-ds/datapackage.yaml").read_text(
        encoding="utf-8"
    )
    parsed_dp = pyyaml.safe_load(dp)
    assert parsed_dp["name"] == "fixture-ds"
    assert all(
        r["hash"].startswith("sha256:") and isinstance(r["bytes"], int)
        for r in parsed_dp["resources"]
    )
    r1 = next(r for r in parsed_dp["resources"] if r["name"] == "r1")
    assert r1["hash"] == (
        "sha256:a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"
    )
    assert r1["bytes"] == 12

    assert (commons / "datasets/fixture-ds/recipe/README.md").is_file()

    commit_count = subprocess.run(
        ["git", "-C", str(commons), "rev-list", "--count", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert commit_count == "3"

    tags = subprocess.run(
        ["git", "-C", str(commons), "tag", "-l"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip().splitlines()
    assert tags == ["dataset/fixture-ds/1.0.0"]

    overlay = (proj / "overlays/datasets/fixture-ds.md").read_text(encoding="utf-8")
    assert "overlay_of: dataset:fixture-ds" in overlay
    assert overlay.startswith("---\n")
    overlay_frontmatter = pyyaml.safe_load(overlay.split("---", 2)[1])
    assert overlay_frontmatter["pin_version"] == "1.0.0"

    data_yaml = tmp_path / ".config" / "science" / "data.yaml"
    assert data_yaml.is_file()
    parsed_yaml = pyyaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    assert parsed_yaml["fixture-ds"] == str(proj / "data/fixture-ds")
    backups = list((tmp_path / ".config" / "science").glob("data.yaml.bak.*"))
    assert len(backups) == 1
