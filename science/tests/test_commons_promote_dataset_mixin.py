"""End-to-end CLI tests for `science commons promote dataset --mixin`."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.commons.cli import commons_group


def _make_project_tree(tmp_path: Path) -> Path:
    """Build a minimal project source tree with one bulk RNA-seq dataset,
    committed to git so discovery's `git ls-files` finds it."""
    proj = tmp_path / "proj-rnaseq"
    (proj / "doc" / "datasets").mkdir(parents=True)
    (proj / "data" / "mockrna").mkdir(parents=True)

    (proj / "doc" / "datasets" / "data-mockrna.md").write_text(
        """---
id: dataset:mockrna
type: dataset
title: Mock RNA-seq dataset
description: Synthetic fixture for Phase H CLI tests.
datapackage: data/mockrna/datapackage.json
origin: external
tier: use-now
access:
  level: public
  verified: true
created: "2026-05-19"
updated: "2026-05-19"
species: ["Homo sapiens"]
assay: bulk-rnaseq
n_rows: 20530
n_cols: 100
value_dtype: int32
feature_axis: rows
---

# Mock RNA-seq

Body content.
""",
        encoding="utf-8",
    )
    (proj / "data" / "mockrna" / "datapackage.json").write_text(
        json.dumps(
            {
                "name": "mockrna",
                "resources": [
                    {
                        "name": "counts",
                        "path": "counts.tsv",
                        "format": "tsv",
                        "mediatype": "text/tab-separated-values",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (proj / "data" / "mockrna" / "counts.tsv").write_text("gene\ts1\n", encoding="utf-8")

    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        [
            "git", "-C", str(proj),
            "-c", "user.email=t@t",
            "-c", "user.name=t",
            "commit", "-q", "-m", "init",
        ],
        check=True,
    )
    return proj


def _init_repo(root: Path) -> None:
    """Init a git repo and set a local user identity."""
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


def _setup_proj_and_commons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    """Build proj tree + commons layout with everything apply_promote needs."""
    proj = _make_project_tree(tmp_path)

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

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SCIENCE_CONFIG_DIR", raising=False)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj-rnaseq": proj}[slug],
    )
    return proj, commons


def test_promote_dataset_with_matrix_and_rnaseq_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promote a bulk-rnaseq dataset with --mixin bio.matrix --mixin bio.rnaseq.
    Canonical entity.md carries the four-segment schema_profile and the bio
    fields in canonical (not overlay)."""
    proj, commons = _setup_proj_and_commons(tmp_path, monkeypatch)

    result = CliRunner().invoke(
        commons_group,
        [
            "promote",
            "dataset",
            "--from",
            "proj-rnaseq",
            "--slug",
            "mockrna",
            "--mixin",
            "bio.matrix",
            "--mixin",
            "bio.rnaseq",
            "--apply",
        ],
    )
    assert result.exit_code == 0, result.output

    entity_path = commons / "datasets" / "mockrna" / "entity.md"
    assert entity_path.is_file(), f"expected canonical entity.md at {entity_path}"
    entity = entity_path.read_text()
    assert (
        "schema_profile: "
        "science-entity-base/1.0+dataset/1.0+bio.matrix/1.0+bio.rnaseq/1.0"
        in entity
    )
    # Bio fields landed in canonical:
    assert "value_dtype: int32" in entity
    assert "assay: bulk-rnaseq" in entity
    assert "feature_axis: rows" in entity
    assert "Homo sapiens" in entity

    overlay = (proj / "doc" / "datasets" / "data-mockrna.md").read_text(
        encoding="utf-8"
    )
    assert "assay: bulk-rnaseq" not in overlay
    assert "value_dtype: int32" not in overlay
    assert "feature_axis: rows" not in overlay
    assert "Homo sapiens" not in overlay
