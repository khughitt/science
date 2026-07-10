"""End-to-end: workflow run -> register-run -> downstream plan-gate accepts result."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from conftest import REGISTER_RUN_EXECUTION_FRONTMATTER, seed_git_repo
from science_tool.cli import main as science_cli


def _seed_full_pipeline(root: Path) -> None:
    # register-run derives seed_policy from the workflow's steps; the project must
    # be loadable and carry a workflow/workflow-step/method trio. A deterministic
    # method derives seed_policy.kind == "deterministic", step_seeds == {}.
    (root / "science.yaml").write_text(
        "name: e2e-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )
    (root / "entities" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / "entities" / "workflows" / "toy.md").write_text(
        '---\nid: "workflow:toy"\nkind: "workflow"\ntitle: "Toy"\n'
        "outputs:\n"
        '  - slug: "result"\n    title: "Result"\n    resource_names: ["result"]\n    ontology_terms: []\n---\n',
        encoding="utf-8",
    )
    (root / "entities" / "methods").mkdir(parents=True, exist_ok=True)
    (root / "entities" / "methods" / "const.md").write_text(
        '---\nid: "method:const"\nkind: "method"\ntitle: "Const"\nstochasticity: "deterministic"\n---\n',
        encoding="utf-8",
    )
    (root / "entities" / "workflow-steps").mkdir(parents=True, exist_ok=True)
    (root / "entities" / "workflow-steps" / "s1.md").write_text(
        '---\nid: "workflow-step:s1"\nkind: "workflow-step"\ntitle: "S1"\n'
        'workflow: "workflow:toy"\nmethod: "method:const"\n---\n',
        encoding="utf-8",
    )
    (root / "entities" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "entities" / "datasets" / "src.md").write_text(
        '---\nid: "dataset:src"\nkind: "dataset"\ntitle: "Src"\norigin: "external"\n'
        'datapackage: "data/src/datapackage.yaml"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://s"}\n'
        "---\n",
        encoding="utf-8",
    )
    (root / "entities" / "workflow-runs").mkdir(parents=True, exist_ok=True)
    (root / "entities" / "workflow-runs" / "toy-r1.md").write_text(
        '---\nid: "workflow-run:toy-r1"\nkind: "workflow-run"\ntitle: "Toy r1"\n'
        'workflow: "workflow:toy"\nproduces: []\ninputs: ["dataset:src"]\n'
        'git_commit: "abc"\nlast_run: "2026-04-19T12:00:00Z"\n'
        f"{REGISTER_RUN_EXECUTION_FRONTMATTER}"
        "---\n",
        encoding="utf-8",
    )
    (root / "results" / "toy" / "r1").mkdir(parents=True)
    (root / "results" / "toy" / "r1" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0"],
                "name": "toy-r1",
                "resources": [{"name": "result", "path": "result.csv", "format": "csv", "hash": "sha256:result"}],
            }
        ),
        encoding="utf-8",
    )
    (root / "results" / "toy" / "r1" / "result.csv").write_text("col\nval\n", encoding="utf-8")
    seed_git_repo(root)


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
    derived_files = list((tmp_path / "entities" / "datasets").glob("toy-*-result.md"))
    assert len(derived_files) == 1, f"expected 1 derived dataset, got {len(derived_files)}"
    derived_id = f"dataset:{derived_files[0].stem}"
    pass_, halts = check_inputs(tmp_path, [derived_id])
    assert pass_ is True, halts
    # Symmetric edge: src.consumed_by includes workflow-run:toy-r1.
    body = (tmp_path / "entities" / "datasets" / "src.md").read_text()
    assert "workflow-run:toy-r1" in body
