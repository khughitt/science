"""Tests for `science-tool data-package migrate <slug>`."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed_legacy_data_package(root: Path) -> None:
    (root / "doc" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflows" / "wf.md").write_text(
        '---\nid: "workflow:wf"\ntype: "workflow"\ntitle: "WF"\n'
        "outputs:\n"
        '  - slug: "kappa"\n    title: "Kappa"\n    resource_names: ["kappa"]\n    ontology_terms: []\n---\n',
        encoding="utf-8",
    )
    (root / "doc" / "workflow-runs").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflow-runs" / "wf-r1.md").write_text(
        '---\nid: "workflow-run:wf-r1"\ntype: "workflow-run"\ntitle: "WF r1"\n'
        'workflow: "workflow:wf"\nproduces: []\ninputs: []\n'
        'git_commit: "abc1234"\nlast_run: "2026-04-19T12:00:00Z"\n---\n',
        encoding="utf-8",
    )
    (root / "doc" / "data-packages").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "data-packages" / "old.md").write_text(
        '---\nid: "data-package:old"\ntype: "data-package"\ntitle: "Old DP"\nstatus: "active"\n'
        'manifest: "research/packages/old/datapackage.json"\n'
        'cells: "research/packages/old/cells.json"\n'
        'workflow_run: "workflow-run:wf-r1"\n---\n',
        encoding="utf-8",
    )
    rp_dir = root / "research" / "packages" / "old"
    rp_dir.mkdir(parents=True, exist_ok=True)
    (rp_dir / "datapackage.json").write_text(
        json.dumps(
            {
                "name": "old",
                "title": "Old DP",
                "profile": "science-research-package",
                "version": "0.1",
                "resources": [{"name": "kappa", "path": "kappa.csv", "format": "csv"}],
                "research": {
                    "cells": "cells.json",
                    "figures": [],
                    "vegalite_specs": [],
                    "code_excerpts": [],
                    "provenance": {
                        "workflow": "workflow:wf",
                        "config": "config.yaml",
                        "last_run": "2026-04-19T12:00:00Z",
                        "git_commit": "abc1234",
                        "repository": "",
                        "inputs": [],
                        "scripts": [],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    # Seed run-aggregate datapackage and resource file (register-run preflight requires them).
    rt = root / "results" / "wf" / "r1"
    rt.mkdir(parents=True, exist_ok=True)
    (rt / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0"],
                "name": "wf-r1",
                "resources": [{"name": "kappa", "path": "kappa.csv", "format": "csv"}],
            }
        ),
        encoding="utf-8",
    )
    (rt / "kappa.csv").write_text("col\nval\n", encoding="utf-8")


# ── Task 8.1 ────────────────────────────────────────────────────────────────


def test_migrate_emits_derived_dataset_entity(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    res = CliRunner().invoke(
        science_cli,
        ["data-package", "migrate", "old"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code == 0, res.output
    ds_path = tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md"
    assert ds_path.exists()
    body = ds_path.read_text()
    assert 'origin: "derived"' in body
    assert 'workflow_run: "workflow-run:wf-r1"' in body


def test_migrate_emits_research_package_entity(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    CliRunner().invoke(
        science_cli,
        ["data-package", "migrate", "old"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    rp_path = tmp_path / "research" / "packages" / "old" / "research-package.md"
    assert rp_path.exists()
    body = rp_path.read_text()
    assert 'type: "research-package"' in body
    assert "dataset:wf-wf-r1-kappa" in body


def test_migrate_marks_old_data_package_superseded(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    CliRunner().invoke(
        science_cli,
        ["data-package", "migrate", "old"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    body = (tmp_path / "doc" / "data-packages" / "old.md").read_text()
    assert 'status: "superseded"' in body or "status: superseded" in body
    assert "research-package:old" in body


# ── Task 8.2 ────────────────────────────────────────────────────────────────


def test_migrate_fails_when_workflow_has_no_outputs(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    wf = tmp_path / "doc" / "workflows" / "wf.md"
    wf.write_text(
        '---\nid: "workflow:wf"\ntype: "workflow"\ntitle: "WF"\n---\n',
        encoding="utf-8",
    )
    res = CliRunner().invoke(
        science_cli,
        ["data-package", "migrate", "old"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code != 0
    assert "outputs" in (res.output + (res.stderr if hasattr(res, "stderr") else ""))


# ── Task 8.3 ────────────────────────────────────────────────────────────────


def test_migrate_idempotent(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    runner = CliRunner()
    runner.invoke(science_cli, ["data-package", "migrate", "old"], env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    snap1 = (tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md").read_text()
    rp_snap1 = (tmp_path / "research" / "packages" / "old" / "research-package.md").read_text()
    runner.invoke(science_cli, ["data-package", "migrate", "old"], env={"SCIENCE_PROJECT_ROOT": str(tmp_path)})
    snap2 = (tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md").read_text()
    rp_snap2 = (tmp_path / "research" / "packages" / "old" / "research-package.md").read_text()
    assert snap1 == snap2
    assert rp_snap1 == rp_snap2


# ── Task 8.3b ───────────────────────────────────────────────────────────────


def test_migrate_dry_run_writes_nothing(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    res = CliRunner().invoke(
        science_cli,
        ["data-package", "migrate", "old", "--dry-run"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    assert "wf-wf-r1-kappa" in res.output
    assert "research-package:old" in res.output or "old/research-package.md" in res.output
    assert not (tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md").exists()
    assert not (tmp_path / "research" / "packages" / "old" / "research-package.md").exists()
    body = (tmp_path / "doc" / "data-packages" / "old.md").read_text()
    assert 'status: "active"' in body or "status: active" in body


def test_migrate_all_iterates_every_unmigrated(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    (tmp_path / "doc" / "data-packages" / "old2.md").write_text(
        '---\nid: "data-package:old2"\ntype: "data-package"\ntitle: "Old DP 2"\nstatus: "active"\n'
        'manifest: "research/packages/old2/datapackage.json"\n'
        'cells: "research/packages/old2/cells.json"\n'
        'workflow_run: "workflow-run:wf-r1"\n---\n',
        encoding="utf-8",
    )
    rp2 = tmp_path / "research" / "packages" / "old2"
    rp2.mkdir(parents=True, exist_ok=True)
    (rp2 / "datapackage.json").write_text(
        json.dumps(
            {
                "name": "old2",
                "title": "Old2",
                "profile": "science-research-package",
                "version": "0.1",
                "resources": [{"name": "kappa", "path": "kappa.csv", "format": "csv"}],
                "research": {
                    "cells": "cells.json",
                    "figures": [],
                    "vegalite_specs": [],
                    "code_excerpts": [],
                    "provenance": {
                        "workflow": "workflow:wf",
                        "config": "c",
                        "last_run": "2026-04-19",
                        "git_commit": "a",
                        "repository": "",
                        "inputs": [],
                        "scripts": [],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    res = CliRunner().invoke(
        science_cli,
        ["data-package", "migrate", "--all"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    for slug in ("old", "old2"):
        body = (tmp_path / "doc" / "data-packages" / f"{slug}.md").read_text()
        assert "superseded" in body
    assert (tmp_path / "research" / "packages" / "old" / "research-package.md").exists()
    assert (tmp_path / "research" / "packages" / "old2" / "research-package.md").exists()


# ── Task 8.4 ────────────────────────────────────────────────────────────────


def test_data_package_list_lists_unmigrated(tmp_path: Path) -> None:
    _seed_legacy_data_package(tmp_path)
    res = CliRunner().invoke(
        science_cli,
        ["data-package", "list"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code == 0
    assert "data-package:old" in res.output
