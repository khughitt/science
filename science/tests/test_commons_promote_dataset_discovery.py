from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


FIXTURE_PROJECT = Path(__file__).parent / "fixtures" / "promote" / "proj-dataset"
DATASET_MD = Path("doc/datasets/data-fixture-ds.md")


def _copy_dataset_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    proj = tmp_path / "proj-dataset"
    shutil.copytree(FIXTURE_PROJECT, proj)
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(proj),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        check=True,
    )
    monkeypatch.setattr("science_tool.commons.promote.resolve_project_by_id", lambda _slug: proj)
    return proj


def _replace_in_dataset_md(proj: Path, old: str, new: str = "") -> None:
    path = proj / DATASET_MD
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_well_formed_fixture_is_discovered(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_DATASET, discover_candidates

    _copy_dataset_project(tmp_path, monkeypatch)

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)

    assert "fixture-ds" in discovery.candidates_by_slug
    assert discovery.failed_candidates == []
    [candidate] = discovery.candidates_by_slug["fixture-ds"]
    assert candidate.datapackage_source_path == candidate.project_root / "data/fixture-ds/datapackage.json"
    assert candidate.datapackage_doc is not None
    assert candidate.datapackage_doc["name"] == "fixture-ds"


def test_missing_datapackage_field_fails_candidate(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_DATASET, discover_candidates

    proj = _copy_dataset_project(tmp_path, monkeypatch)
    _replace_in_dataset_md(proj, "datapackage: data/fixture-ds/datapackage.json\n")

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)

    assert discovery.candidates_by_slug == {}
    assert len(discovery.failed_candidates) == 1
    fc = discovery.failed_candidates[0]
    assert fc.slug == "fixture-ds"
    assert "datapackage" in fc.error_message


def test_missing_resource_file_fails_candidate(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_DATASET, discover_candidates

    proj = _copy_dataset_project(tmp_path, monkeypatch)
    (proj / "data/fixture-ds/r1.txt").unlink()

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)

    assert discovery.candidates_by_slug == {}
    fc = discovery.failed_candidates[0]
    assert fc.error_class == "PromoteResourceMissingError"
    assert "r1.txt" in fc.error_message


@pytest.mark.parametrize(
    ("field", "frontmatter"),
    [
        ("origin", "origin: external\n"),
        ("tier", "tier: evaluate-next\n"),
        (
            "access",
            "access:\n  level: public\n  verified: true\n",
        ),
    ],
)
def test_missing_required_dataset_mixin_fields_fail(
    tmp_path,
    monkeypatch,
    field: str,
    frontmatter: str,
) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_DATASET, discover_candidates

    proj = _copy_dataset_project(tmp_path, monkeypatch)
    _replace_in_dataset_md(proj, frontmatter)

    discovery = discover_candidates(["proj-dataset"], PROMOTE_KIND_DATASET)

    assert discovery.candidates_by_slug == {}
    assert len(discovery.failed_candidates) == 1
    assert field in discovery.failed_candidates[0].error_message
