"""Tests for `science-tool dataset reconcile` command (Task 7.6)."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed(tmp_path: Path, *, entity_license: str, runtime_license: str) -> None:
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    (tmp_path / "doc" / "datasets" / "x.md").write_text(
        '---\nid: "dataset:x"\ntype: "dataset"\ntitle: "X"\norigin: "external"\n'
        f'license: "{entity_license}"\n'
        'datapackage: "data/x/datapackage.yaml"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}\n'
        "---\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "x").mkdir(parents=True)
    (tmp_path / "data" / "x" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0"],
                "name": "x",
                "license": runtime_license,
                "resources": [{"name": "r", "path": "r.csv"}],
            }
        ),
        encoding="utf-8",
    )


def test_reconcile_in_sync_exits_zero(tmp_path: Path) -> None:
    _seed(tmp_path, entity_license="CC-BY-4.0", runtime_license="CC-BY-4.0")
    res = CliRunner().invoke(
        science_cli,
        ["dataset", "reconcile", "x"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code == 0


def test_reconcile_drift_exits_nonzero(tmp_path: Path) -> None:
    _seed(tmp_path, entity_license="CC-BY-4.0", runtime_license="CC0-1.0")
    res = CliRunner().invoke(
        science_cli,
        ["dataset", "reconcile", "x"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code != 0
    assert "license" in res.output


def test_reconcile_missing_entity_exits_2(tmp_path: Path) -> None:
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    res = CliRunner().invoke(
        science_cli,
        ["dataset", "reconcile", "nonexistent"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code == 2
