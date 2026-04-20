"""Tests for `science-tool dataset register-run` command (Tasks 7.2 – 7.5b)."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed_workflow_and_run(
    root: Path,
    *,
    run_resources: list[dict],
    workflow_outputs: list[dict] | None = None,
) -> None:
    """Seed a workflow + run fixture.

    If ``workflow_outputs`` is not provided, outputs are inferred from
    ``run_resources`` (one output per resource, slug = resource name).
    """
    if workflow_outputs is None:
        workflow_outputs = [
            {
                "slug": r["name"],
                "title": r["name"].capitalize(),
                "resource_names": [r["name"]],
                "ontology_terms": [],
            }
            for r in run_resources
        ]
    wf_dir = root / "doc" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    outputs_yaml = "".join(
        f'  - slug: "{o["slug"]}"\n'
        f'    title: "{o["title"]}"\n'
        f"    resource_names: {o['resource_names']!r}\n"
        f"    ontology_terms: {o.get('ontology_terms', [])!r}\n"
        for o in workflow_outputs
    )
    (wf_dir / "wf.md").write_text(
        f'---\nid: "workflow:wf"\ntype: "workflow"\ntitle: "WF"\noutputs:\n{outputs_yaml}---\n',
        encoding="utf-8",
    )
    runs_dir = root / "doc" / "workflow-runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "wf-r1.md").write_text(
        "---\n"
        'id: "workflow-run:wf-r1"\n'
        'type: "workflow-run"\n'
        'title: "WF r1"\n'
        'workflow: "workflow:wf"\n'
        "produces: []\n"
        "inputs: []\n"
        "---\n",
        encoding="utf-8",
    )
    rt_dir = root / "results" / "wf" / "r1"
    rt_dir.mkdir(parents=True, exist_ok=True)
    (rt_dir / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0"],
                "name": "wf-r1",
                "resources": run_resources,
            }
        ),
        encoding="utf-8",
    )


def _seed_resource_files(root: Path, names: list[str]) -> None:
    rt_root = root / "results" / "wf" / "r1"
    for name in names:
        (rt_root / f"{name}.csv").write_text("col\nval\n", encoding="utf-8")


# ── Task 7.2: per-output datapackages ──────────────────────────────────────


def test_register_run_writes_per_output_datapackages(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "kappa", "path": "kappa.csv", "format": "csv", "bytes": 100, "hash": "sha256:a"},
            {"name": "structural", "path": "structural.csv", "format": "csv", "bytes": 200, "hash": "sha256:b"},
        ],
        workflow_outputs=[
            {"slug": "kappa", "title": "Kappa", "resource_names": ["kappa"], "ontology_terms": []},
            {"slug": "structural", "title": "Structural", "resource_names": ["structural"], "ontology_terms": []},
        ],
    )
    _seed_resource_files(tmp_path, ["kappa", "structural"])
    runner = CliRunner()
    res = runner.invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code == 0, res.output
    kappa_dp = tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml"
    structural_dp = tmp_path / "results" / "wf" / "r1" / "structural" / "datapackage.yaml"
    assert kappa_dp.exists()
    assert structural_dp.exists()
    kappa = yaml.safe_load(kappa_dp.read_text())
    assert [r["name"] for r in kappa["resources"]] == ["kappa"]
    assert kappa["basepath"] == ".."
    assert kappa["resources"][0]["path"] == "kappa.csv"


def test_per_output_datapackage_paths_resolve_to_real_files(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "kappa", "path": "kappa.csv", "format": "csv"},
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])
    CliRunner().invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
        catch_exceptions=False,
    )
    dp_path = tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml"
    dp = yaml.safe_load(dp_path.read_text())
    resolved = (dp_path.parent / dp["basepath"] / dp["resources"][0]["path"]).resolve()
    assert resolved.exists()


def test_register_run_fails_when_resource_file_missing(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "kappa", "path": "kappa.csv", "format": "csv"},
        ],
    )
    # intentionally NOT seeding resource files
    res = CliRunner().invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code != 0
    output_lower = res.output.lower()
    assert "kappa.csv" in res.output or "not exist" in output_lower or "no such file" in output_lower


# ── Task 7.3: derived dataset entities ────────────────────────────────────


def test_register_run_writes_dataset_entities(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "kappa", "path": "kappa.csv", "format": "csv"},
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])
    runner = CliRunner()
    res = runner.invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code == 0, res.output
    ds_path = tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md"
    assert ds_path.exists()
    body = ds_path.read_text()
    assert 'origin: "derived"' in body
    assert 'workflow_run: "workflow-run:wf-r1"' in body
    assert 'datapackage: "results/wf/r1/kappa/datapackage.yaml"' in body


# ── Task 7.4: symmetric edges ──────────────────────────────────────────────


def test_register_run_appends_to_workflow_run_produces(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "kappa", "path": "kappa.csv", "format": "csv"},
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])
    CliRunner().invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    body = (tmp_path / "doc" / "workflow-runs" / "wf-r1.md").read_text()
    assert "dataset:wf-wf-r1-kappa" in body


def test_register_run_appends_workflow_run_to_upstream_consumed_by(tmp_path: Path) -> None:
    (tmp_path / "doc" / "datasets").mkdir(parents=True, exist_ok=True)
    (tmp_path / "doc" / "datasets" / "up.md").write_text(
        '---\nid: "dataset:up"\ntype: "dataset"\ntitle: "Up"\norigin: "external"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}\n'
        "consumed_by: []\n---\n",
        encoding="utf-8",
    )
    _seed_workflow_and_run(tmp_path, run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}])
    _seed_resource_files(tmp_path, ["kappa"])
    runs = tmp_path / "doc" / "workflow-runs" / "wf-r1.md"
    runs.write_text(runs.read_text().replace("inputs: []", 'inputs: ["dataset:up"]'), encoding="utf-8")
    CliRunner().invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    body = (tmp_path / "doc" / "datasets" / "up.md").read_text()
    assert "workflow-run:wf-r1" in body


def test_append_preserves_inline_comments(tmp_path: Path) -> None:
    from science_tool.datasets_register import _append_yaml_list_item

    p = tmp_path / "x.md"
    original = """---
id: "dataset:x"  # the dataset
type: "dataset"
# A leading comment.
consumed_by: []
title: "X"
---
Body.
"""
    p.write_text(original, encoding="utf-8")
    _append_yaml_list_item(p, "consumed_by", "plan:p1")
    after = p.read_text()
    assert "# the dataset" in after
    assert "# A leading comment." in after
    assert "plan:p1" in after
    assert "Body." in after


def test_append_handles_block_form_list(tmp_path: Path) -> None:
    from science_tool.datasets_register import _append_yaml_list_item

    p = tmp_path / "y.md"
    p.write_text(
        '---\nid: "dataset:y"\ntype: "dataset"\ntitle: "Y"\nconsumed_by:\n  - "plan:existing"\n---\n',
        encoding="utf-8",
    )
    _append_yaml_list_item(p, "consumed_by", "plan:p2")
    body = p.read_text()
    assert '- "plan:existing"' in body
    assert '- "plan:p2"' in body


def test_append_idempotent(tmp_path: Path) -> None:
    from science_tool.datasets_register import _append_yaml_list_item

    p = tmp_path / "z.md"
    p.write_text(
        '---\nid: "dataset:z"\ntype: "dataset"\ntitle: "Z"\nconsumed_by: ["plan:p1"]\n---\n',
        encoding="utf-8",
    )
    snapshot = p.read_text()
    _append_yaml_list_item(p, "consumed_by", "plan:p1")
    assert p.read_text() == snapshot


# ── Task 7.5: idempotency ─────────────────────────────────────────────────


def test_register_run_idempotent(tmp_path: Path) -> None:
    _seed_workflow_and_run(tmp_path, run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}])
    _seed_resource_files(tmp_path, ["kappa"])
    runner = CliRunner()
    res1 = runner.invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res1.exit_code == 0
    rt1 = (tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml").read_text()
    res2 = runner.invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res2.exit_code == 0
    rt2 = (tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml").read_text()
    assert rt1 == rt2  # per-output dp unchanged
    runs_body = (tmp_path / "doc" / "workflow-runs" / "wf-r1.md").read_text()
    assert runs_body.count("dataset:wf-wf-r1-kappa") == 1  # produces deduplicated


# ── Task 7.5b: parallel runs coexist ──────────────────────────────────────


def test_repeated_runs_produce_parallel_active_datasets(tmp_path: Path) -> None:
    _seed_workflow_and_run(tmp_path, run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}])
    _seed_resource_files(tmp_path, ["kappa"])
    runner = CliRunner()
    runner.invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
        catch_exceptions=False,
    )
    from science_tool.datasets_register import _append_yaml_list_item

    _append_yaml_list_item(tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md", "consumed_by", "plan:p1")
    runs_dir = tmp_path / "doc" / "workflow-runs"
    (runs_dir / "wf-r2.md").write_text(
        "---\n"
        'id: "workflow-run:wf-r2"\n'
        'type: "workflow-run"\n'
        'title: "WF r2"\n'
        'workflow: "workflow:wf"\n'
        "produces: []\n"
        "inputs: []\n"
        'git_commit: "def"\n'
        'last_run: "2026-04-20T12:00:00Z"\n'
        "---\n",
        encoding="utf-8",
    )
    rt2 = tmp_path / "results" / "wf" / "r2"
    rt2.mkdir(parents=True)
    (rt2 / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0"],
                "name": "wf-r2",
                "resources": [{"name": "kappa", "path": "kappa.csv", "format": "csv"}],
            }
        ),
        encoding="utf-8",
    )
    (rt2 / "kappa.csv").write_text("col\nval2\n", encoding="utf-8")
    runner.invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r2"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
        catch_exceptions=False,
    )
    r1 = (tmp_path / "doc" / "datasets" / "wf-wf-r1-kappa.md").read_text()
    r2 = (tmp_path / "doc" / "datasets" / "wf-wf-r2-kappa.md").read_text()
    assert 'status: "active"' in r1
    assert 'status: "active"' in r2
    assert "plan:p1" in r1
    assert "superseded_by" not in r1
    assert "superseded_by" not in r2
