"""End-to-end: legacy data-package -> migrate -> graph build (strict) succeeds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed(root: Path) -> None:
    """Carve out a legacy data-package + matching workflow + run."""
    (root / "doc" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflows" / "wf.md").write_text(
        '---\nid: "workflow:wf"\ntype: "workflow"\ntitle: "WF"\n'
        "outputs:\n"
        '  - slug: "result"\n    title: "Result"\n    resource_names: ["result"]\n    ontology_terms: []\n---\n',
        encoding="utf-8",
    )
    (root / "doc" / "workflow-runs").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflow-runs" / "wf-r1.md").write_text(
        '---\nid: "workflow-run:wf-r1"\ntype: "workflow-run"\ntitle: "r1"\n'
        'workflow: "workflow:wf"\nproduces: []\ninputs: []\n'
        'git_commit: "a"\nlast_run: "2026-04-19T00:00:00Z"\n---\n',
        encoding="utf-8",
    )
    (root / "doc" / "data-packages").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "data-packages" / "old.md").write_text(
        '---\nid: "data-package:old"\ntype: "data-package"\ntitle: "Old"\nstatus: "active"\n'
        'workflow_run: "workflow-run:wf-r1"\n'
        'manifest: "research/packages/old/datapackage.json"\n'
        'cells: "research/packages/old/cells.json"\n---\n',
        encoding="utf-8",
    )
    rp = root / "research" / "packages" / "old"
    rp.mkdir(parents=True, exist_ok=True)
    (rp / "datapackage.json").write_text(
        json.dumps(
            {
                "name": "old",
                "title": "Old",
                "profile": "science-research-package",
                "version": "0.1",
                "resources": [{"name": "result", "path": "result.csv", "format": "csv"}],
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
    # Also seed run-aggregate and resource file (register-run preflight requires them).
    rt = root / "results" / "wf" / "r1"
    rt.mkdir(parents=True)
    (rt / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0"],
                "name": "wf-r1",
                "resources": [{"name": "result", "path": "result.csv", "format": "csv"}],
            }
        ),
        encoding="utf-8",
    )
    (rt / "result.csv").write_text("col\nval\n", encoding="utf-8")


def test_strict_build_fails_then_migrate_unblocks(tmp_path: Path) -> None:
    _seed(tmp_path)
    runner = CliRunner()
    # Strict graph build fails first.
    from science_tool.graph.materialize import materialize_graph

    with pytest.raises(RuntimeError, match="data-package:old"):
        materialize_graph(tmp_path, strict=True)
    # Migrate.
    res = runner.invoke(
        science_cli,
        ["data-package", "migrate", "old"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
        catch_exceptions=False,
    )
    assert res.exit_code == 0, res.output
    # Now strict build passes.
    materialize_graph(tmp_path, strict=True)
    # Verify research-package exists with correct symmetric backlink.
    rp_path = tmp_path / "research" / "packages" / "old" / "research-package.md"
    assert rp_path.exists()
    rp_body = rp_path.read_text()
    # The derived dataset slug pattern: <wf>-<run-slug>-<output>
    # Look for any derived dataset in the displays list:
    derived_files = list((tmp_path / "doc" / "datasets").glob("wf-*-result.md"))
    assert len(derived_files) == 1
    derived_id = f"dataset:{derived_files[0].stem}"
    assert derived_id in rp_body
    ds_body = derived_files[0].read_text()
    assert "research-package:old" in ds_body  # symmetric
