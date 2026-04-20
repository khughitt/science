"""End-to-end: workflow run -> register-run -> downstream plan-gate accepts result."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed_full_pipeline(root: Path) -> None:
    (root / "doc" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflows" / "toy.md").write_text(
        '---\nid: "workflow:toy"\ntype: "workflow"\ntitle: "Toy"\n'
        "outputs:\n"
        '  - slug: "result"\n    title: "Result"\n    resource_names: ["result"]\n    ontology_terms: []\n---\n',
        encoding="utf-8",
    )
    (root / "doc" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "datasets" / "src.md").write_text(
        '---\nid: "dataset:src"\ntype: "dataset"\ntitle: "Src"\norigin: "external"\n'
        'datapackage: "data/src/datapackage.yaml"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://s"}\n'
        "---\n",
        encoding="utf-8",
    )
    (root / "doc" / "workflow-runs").mkdir(parents=True, exist_ok=True)
    (root / "doc" / "workflow-runs" / "toy-r1.md").write_text(
        '---\nid: "workflow-run:toy-r1"\ntype: "workflow-run"\ntitle: "Toy r1"\n'
        'workflow: "workflow:toy"\nproduces: []\ninputs: ["dataset:src"]\n'
        'git_commit: "abc"\nlast_run: "2026-04-19T12:00:00Z"\n---\n',
        encoding="utf-8",
    )
    (root / "results" / "toy" / "r1").mkdir(parents=True)
    (root / "results" / "toy" / "r1" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0"],
                "name": "toy-r1",
                "resources": [{"name": "result", "path": "result.csv", "format": "csv"}],
            }
        ),
        encoding="utf-8",
    )
    (root / "results" / "toy" / "r1" / "result.csv").write_text("col\nval\n", encoding="utf-8")


def test_register_run_then_gate_accepts_downstream(tmp_path: Path) -> None:
    _seed_full_pipeline(tmp_path)
    runner = CliRunner()
    res = runner.invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:toy-r1"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
        catch_exceptions=False,
    )
    assert res.exit_code == 0, res.output
    # Now the derived dataset exists; gate accepts it.
    from science_tool.plan_gate import check_inputs

    # The dataset slug is <workflow>-<run>-<output> (where run slug excludes workflow prefix
    # in the current implementation; verify what register-run actually wrote).
    # Find the actual derived dataset file:
    derived_files = list((tmp_path / "doc" / "datasets").glob("toy-*-result.md"))
    assert len(derived_files) == 1, f"expected 1 derived dataset, got {len(derived_files)}"
    derived_id = f"dataset:{derived_files[0].stem}"
    pass_, halts = check_inputs(tmp_path, [derived_id])
    assert pass_ is True, halts
    # Symmetric edge: src.consumed_by includes workflow-run:toy-r1.
    body = (tmp_path / "doc" / "datasets" / "src.md").read_text()
    assert "workflow-run:toy-r1" in body
