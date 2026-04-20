"""Tests for `science-tool dataset list --origin` filter (Task 7.1)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed_two_origins(root: Path) -> None:
    (root / "doc" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "datasets" / "ext.md").write_text(
        '---\nid: "dataset:ext"\ntype: "dataset"\ntitle: "Ext"\norigin: "external"\n'
        'access: {level: "public", verified: false}\n---\n',
        encoding="utf-8",
    )
    (root / "doc" / "datasets" / "der.md").write_text(
        '---\nid: "dataset:der"\ntype: "dataset"\ntitle: "Der"\norigin: "derived"\n'
        'derivation: {workflow: "workflow:w", workflow_run: "workflow-run:r", git_commit: "a", config_snapshot: "c", produced_at: "t", inputs: []}\n'
        'datapackage: "results/w/r/x/datapackage.yaml"\n---\n',
        encoding="utf-8",
    )


def test_dataset_list_origin_filter(tmp_path: Path) -> None:
    _seed_two_origins(tmp_path)
    runner = CliRunner()
    res = runner.invoke(
        science_cli,
        ["dataset", "list", "--origin", "external"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code == 0
    assert "dataset:ext" in res.output
    assert "dataset:der" not in res.output

    res2 = runner.invoke(
        science_cli,
        ["dataset", "list", "--origin", "derived"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert "dataset:der" in res2.output
    assert "dataset:ext" not in res2.output


def test_dataset_list_no_filter_shows_all(tmp_path: Path) -> None:
    _seed_two_origins(tmp_path)
    runner = CliRunner()
    res = runner.invoke(
        science_cli,
        ["dataset", "list"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code == 0
    assert "dataset:ext" in res.output
    assert "dataset:der" in res.output
