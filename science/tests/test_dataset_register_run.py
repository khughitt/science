"""Tests for `science dataset register-run` command (Tasks 7.2 – 7.5b)."""

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
    run_inputs: list[str] | None = None,
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
    wf_dir = root / "entities" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    outputs_yaml = yaml.safe_dump(workflow_outputs, sort_keys=False)
    outputs_yaml = "".join(f"  {line}" if line.strip() else line for line in outputs_yaml.splitlines(True))
    (wf_dir / "wf.md").write_text(
        f'---\nid: "workflow:wf"\ntype: "workflow"\ntitle: "WF"\noutputs:\n{outputs_yaml}---\n',
        encoding="utf-8",
    )
    runs_dir = root / "entities" / "workflow-runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "wf-r1.md").write_text(
        "---\n"
        'id: "workflow-run:wf-r1"\n'
        'type: "workflow-run"\n'
        'title: "WF r1"\n'
        'workflow: "workflow:wf"\n'
        "produces: []\n"
        f"inputs: {run_inputs or []!r}\n"
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


def _seed_dataset(root: Path, slug: str, identity_context: dict | None = None) -> None:
    dataset: dict = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0",
        "id": f"dataset:{slug}",
        "type": "dataset",
        "title": slug,
        "origin": "external",
        "consumed_by": [],
    }
    if identity_context is not None:
        dataset["identity_context"] = identity_context
    body = yaml.safe_dump(dataset, sort_keys=False)
    path = root / "entities" / "datasets" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{body}---\n", encoding="utf-8")


def _frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])


def _run_register(root: Path):
    return CliRunner().invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        env={"SCIENCE_PROJECT_ROOT": str(root)},
    )


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
    # Entity id must not double the workflow-slug prefix, and must match the
    # per-output datapackage name (`wf-r1-kappa`, see results/wf/r1/kappa).
    ds_path = tmp_path / "entities" / "datasets" / "wf-r1-kappa.md"
    assert ds_path.exists()
    assert not (tmp_path / "entities" / "datasets" / "wf-wf-r1-kappa.md").exists()
    body = ds_path.read_text()
    assert 'id: "dataset:wf-r1-kappa"' in body
    assert 'origin: "derived"' in body
    assert 'workflow_run: "workflow-run:wf-r1"' in body
    assert 'datapackage: "results/wf/r1/kappa/datapackage.yaml"' in body


def test_register_run_copies_literal_output_identity_to_derived_entity(tmp_path: Path) -> None:
    identity = {
        "taxon": 9606,
        "assembly": {
            "label": "UNKNOWN",
            "registry": "dataset:assembly-registry",
            "resolution_status": "declared_unresolved",
        },
    }
    schema_profile = "science-entity-base/1.0+dataset/1.0+bio.cna/1.0+bio.identity_context/1.0"
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "kappa", "path": "kappa.csv", "format": "csv"},
        ],
        workflow_outputs=[
            {
                "slug": "kappa",
                "title": "Kappa",
                "resource_names": ["kappa"],
                "ontology_terms": [],
                "schema_profile": schema_profile,
                "identity": identity,
            },
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])

    res = CliRunner().invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )

    assert res.exit_code == 0, res.output
    ds_path = tmp_path / "entities" / "datasets" / "wf-r1-kappa.md"
    frontmatter = yaml.safe_load(ds_path.read_text(encoding="utf-8").split("---", 2)[1])
    assert frontmatter["schema_profile"] == schema_profile
    assert frontmatter["identity_context"] == identity


def test_register_run_rejects_profile_required_identity_after_resolution_before_writing(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "kappa", "path": "kappa.csv", "format": "csv"},
        ],
        workflow_outputs=[
            {
                "slug": "kappa",
                "title": "Kappa",
                "resource_names": ["kappa"],
                "ontology_terms": [],
                "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.cna/1.0",
                "identity": {"taxon": 9606},
            },
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])

    res = _run_register(tmp_path)

    assert res.exit_code != 0
    assert "identity" in res.output
    assert "assembly" in res.output
    assert not (tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml").exists()
    assert not (tmp_path / "entities" / "datasets" / "wf-r1-kappa.md").exists()


def test_register_run_rejects_blank_output_schema_profile(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "kappa", "path": "kappa.csv", "format": "csv"},
        ],
        workflow_outputs=[
            {
                "slug": "kappa",
                "title": "Kappa",
                "resource_names": ["kappa"],
                "ontology_terms": [],
                "schema_profile": "",
            },
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])

    res = CliRunner().invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )

    assert res.exit_code != 0
    assert "schema_profile" in res.output
    assert not (tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml").exists()
    assert not (tmp_path / "entities" / "datasets" / "wf-r1-kappa.md").exists()


def test_register_run_rejects_non_mapping_output_identity_before_writing(tmp_path: Path) -> None:
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[
            {"name": "kappa", "path": "kappa.csv", "format": "csv"},
        ],
        workflow_outputs=[
            {
                "slug": "kappa",
                "title": "Kappa",
                "resource_names": ["kappa"],
                "ontology_terms": [],
                "identity": "not-a-mapping",
            },
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])

    res = CliRunner().invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )

    assert res.exit_code != 0
    assert "identity" in res.output
    assert "Traceback" not in res.output
    assert not (tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml").exists()
    assert not (tmp_path / "entities" / "datasets" / "wf-r1-kappa.md").exists()


# ── Task P3.2: register-run identity resolution/propagation ───────────────


def test_register_run_bare_inherit_uses_shared_input_identity(tmp_path: Path) -> None:
    identity = {
        "taxon": 9606,
        "assembly": {
            "seqcol_digest": "SQ.GRCh38",
            "registry": "dataset:assembly-registry",
            "resolution_status": "resolved",
        },
    }
    _seed_dataset(tmp_path, "up-a", identity)
    _seed_dataset(tmp_path, "up-b", identity)
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}],
        run_inputs=["dataset:up-a", "dataset:up-b"],
        workflow_outputs=[
            {
                "slug": "kappa",
                "title": "Kappa",
                "resource_names": ["kappa"],
                "ontology_terms": [],
                "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.cna/1.0",
                "identity": {"taxon": "inherit", "assembly": "inherit"},
            }
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])

    res = _run_register(tmp_path)

    assert res.exit_code == 0, res.output
    entity = _frontmatter(tmp_path / "entities" / "datasets" / "wf-r1-kappa.md")
    assert entity["identity_context"] == identity
    assert entity["schema_profile"] == ("science-entity-base/1.0+dataset/1.0+bio.cna/1.0+bio.identity_context/1.0")
    datapackage = yaml.safe_load(
        (tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml").read_text(encoding="utf-8")
    )
    assert datapackage["science"]["identity_context"] == identity


def test_register_run_bare_inherit_errors_when_input_identities_disagree(tmp_path: Path) -> None:
    _seed_dataset(tmp_path, "human", {"taxon": 9606})
    _seed_dataset(tmp_path, "mouse", {"taxon": 10090})
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}],
        run_inputs=["dataset:human", "dataset:mouse"],
        workflow_outputs=[
            {
                "slug": "kappa",
                "title": "Kappa",
                "resource_names": ["kappa"],
                "ontology_terms": [],
                "identity": {"taxon": "inherit"},
            }
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])

    res = _run_register(tmp_path)

    assert res.exit_code != 0
    assert "inherit" in res.output
    assert "disagree" in res.output
    assert not (tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml").exists()
    assert not (tmp_path / "entities" / "datasets" / "wf-r1-kappa.md").exists()


def test_register_run_bare_inherit_errors_when_selected_input_lacks_identity_context(tmp_path: Path) -> None:
    _seed_dataset(tmp_path, "identified", {"taxon": 9606})
    _seed_dataset(tmp_path, "unidentified")
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}],
        run_inputs=["dataset:identified", "dataset:unidentified"],
        workflow_outputs=[
            {
                "slug": "kappa",
                "title": "Kappa",
                "resource_names": ["kappa"],
                "ontology_terms": [],
                "identity": {"taxon": "inherit"},
            }
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])

    res = _run_register(tmp_path)

    assert res.exit_code != 0
    assert "inherit" in res.output
    assert "identity_context" in res.output
    assert not (tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml").exists()
    assert not (tmp_path / "entities" / "datasets" / "wf-r1-kappa.md").exists()


def test_register_run_bare_inherit_errors_when_selected_input_lacks_requested_tier(tmp_path: Path) -> None:
    _seed_dataset(
        tmp_path,
        "assembled",
        {
            "taxon": 9606,
            "assembly": {
                "seqcol_digest": "SQ.GRCh38",
                "registry": "dataset:assembly-registry",
                "resolution_status": "resolved",
            },
        },
    )
    _seed_dataset(tmp_path, "taxon-only", {"taxon": 9606})
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}],
        run_inputs=["dataset:assembled", "dataset:taxon-only"],
        workflow_outputs=[
            {
                "slug": "kappa",
                "title": "Kappa",
                "resource_names": ["kappa"],
                "ontology_terms": [],
                "identity": {"assembly": "inherit"},
            }
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])

    res = _run_register(tmp_path)

    assert res.exit_code != 0
    assert "inherit" in res.output
    assert "assembly" in res.output
    assert not (tmp_path / "results" / "wf" / "r1" / "kappa" / "datapackage.yaml").exists()
    assert not (tmp_path / "entities" / "datasets" / "wf-r1-kappa.md").exists()


def test_register_run_inherit_from_selects_named_input_identity(tmp_path: Path) -> None:
    _seed_dataset(tmp_path, "human", {"taxon": 9606})
    _seed_dataset(tmp_path, "mouse", {"taxon": 10090})
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}],
        run_inputs=["dataset:human", "dataset:mouse"],
        workflow_outputs=[
            {
                "slug": "kappa",
                "title": "Kappa",
                "resource_names": ["kappa"],
                "ontology_terms": [],
                "identity": {"taxon": {"inherit": {"from": "dataset:mouse"}}},
            }
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])

    res = _run_register(tmp_path)

    assert res.exit_code == 0, res.output
    entity = _frontmatter(tmp_path / "entities" / "datasets" / "wf-r1-kappa.md")
    assert entity["identity_context"] == {"taxon": 10090}


def test_register_run_inherit_from_ignores_missing_unrelated_lineage_input(tmp_path: Path) -> None:
    _seed_dataset(tmp_path, "source", {"taxon": 9606})
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}],
        run_inputs=["dataset:source", "dataset:missing-unrelated"],
        workflow_outputs=[
            {
                "slug": "kappa",
                "title": "Kappa",
                "resource_names": ["kappa"],
                "ontology_terms": [],
                "identity": {"taxon": {"inherit": {"from": "dataset:source"}}},
            }
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])

    res = _run_register(tmp_path)

    assert res.exit_code == 0, res.output
    entity = _frontmatter(tmp_path / "entities" / "datasets" / "wf-r1-kappa.md")
    assert entity["identity_context"] == {"taxon": 9606}
    assert entity["derivation"]["inputs"] == ["dataset:source", "dataset:missing-unrelated"]


def test_register_run_literal_identity_does_not_load_input_identities(tmp_path: Path) -> None:
    identity = {
        "taxon": 9606,
        "assembly": {
            "label": "UNKNOWN",
            "registry": "dataset:assembly-registry",
            "resolution_status": "declared_unresolved",
        },
    }
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}],
        run_inputs=["dataset:missing-upstream"],
        workflow_outputs=[
            {
                "slug": "kappa",
                "title": "Kappa",
                "resource_names": ["kappa"],
                "ontology_terms": [],
                "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.cna/1.0",
                "identity": identity,
            }
        ],
    )
    _seed_resource_files(tmp_path, ["kappa"])

    res = _run_register(tmp_path)

    assert res.exit_code == 0, res.output
    entity = _frontmatter(tmp_path / "entities" / "datasets" / "wf-r1-kappa.md")
    assert entity["identity_context"] == identity
    assert entity["derivation"]["inputs"] == ["dataset:missing-upstream"]


def test_register_run_proxy_output_preserves_unresolved_proxy_and_routes_sources(tmp_path: Path) -> None:
    _seed_dataset(
        tmp_path,
        "source-segments",
        {
            "taxon": 9606,
            "assembly": {
                "seqcol_digest": "SQ.GRCh38",
                "registry": "dataset:assembly-registry",
                "resolution_status": "resolved",
            },
        },
    )
    _seed_dataset(tmp_path, "cytoband-map")
    proxy = {
        "type": "cytoband_proxy",
        "via": "dataset:cytoband-map",
        "sources": [{"dataset": "dataset:source-segments", "assembly": "inherit"}],
    }
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[{"name": "bands", "path": "bands.csv", "format": "csv"}],
        workflow_outputs=[
            {
                "slug": "bands",
                "title": "Bands",
                "resource_names": ["bands"],
                "ontology_terms": [],
                "identity": {
                    "taxon": {"inherit": {"from": "dataset:source-segments"}},
                    "assembly": {
                        "label": "UNKNOWN",
                        "registry": "dataset:assembly-registry",
                        "resolution_status": "declared_unresolved",
                        "proxy": proxy,
                    },
                },
            }
        ],
    )
    _seed_resource_files(tmp_path, ["bands"])

    res = _run_register(tmp_path)

    assert res.exit_code == 0, res.output
    entity = _frontmatter(tmp_path / "entities" / "datasets" / "wf-r1-bands.md")
    assert entity["identity_context"]["assembly"]["resolution_status"] == "declared_unresolved"
    assert entity["identity_context"]["assembly"]["proxy"] == proxy
    assert entity["derivation"]["inputs"] == ["dataset:source-segments"]
    assert entity["derivation"]["transformations"] == [
        {"kind": "proxy_via", "dataset": "dataset:cytoband-map", "type": "cytoband_proxy"}
    ]
    assert (
        "workflow-run:wf-r1" in _frontmatter(tmp_path / "entities" / "datasets" / "source-segments.md")["consumed_by"]
    )
    assert (
        "workflow-run:wf-r1" not in _frontmatter(tmp_path / "entities" / "datasets" / "cytoband-map.md")["consumed_by"]
    )


def test_register_run_transform_dataset_routes_to_transformations_not_data_inputs(tmp_path: Path) -> None:
    _seed_dataset(
        tmp_path,
        "source",
        {
            "taxon": 9606,
            "assembly": {
                "seqcol_digest": "SQ.GRCh37",
                "registry": "dataset:assembly-registry",
                "resolution_status": "resolved",
            },
        },
    )
    _seed_dataset(tmp_path, "liftover-chain")
    transform = {
        "type": "liftover",
        "from": "GRCh37",
        "method": "chain",
        "dataset": "dataset:liftover-chain",
    }
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[{"name": "lifted", "path": "lifted.csv", "format": "csv"}],
        run_inputs=["dataset:source"],
        workflow_outputs=[
            {
                "slug": "lifted",
                "title": "Lifted",
                "resource_names": ["lifted"],
                "ontology_terms": [],
                "identity": {
                    "taxon": "inherit",
                    "assembly": {
                        "label": "GRCh38",
                        "registry": "dataset:assembly-registry",
                        "resolution_status": "declared_unresolved",
                        "transform": transform,
                    },
                },
            }
        ],
    )
    _seed_resource_files(tmp_path, ["lifted"])

    res = _run_register(tmp_path)

    assert res.exit_code == 0, res.output
    entity = _frontmatter(tmp_path / "entities" / "datasets" / "wf-r1-lifted.md")
    assert entity["identity_context"]["assembly"]["resolution_status"] == "declared_unresolved"
    assert entity["identity_context"]["assembly"]["transform"] == transform
    assert entity["derivation"]["inputs"] == ["dataset:source"]
    assert entity["derivation"]["transformations"] == [
        {
            "kind": "identity_transform",
            "target": "assembly",
            "dataset": "dataset:liftover-chain",
            "type": "liftover",
            "from": "GRCh37",
            "method": "chain",
        }
    ]
    assert "dataset:liftover-chain" not in entity["derivation"]["inputs"]
    assert (
        "workflow-run:wf-r1"
        not in _frontmatter(tmp_path / "entities" / "datasets" / "liftover-chain.md")["consumed_by"]
    )


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
    body = (tmp_path / "entities" / "workflow-runs" / "wf-r1.md").read_text()
    assert "dataset:wf-r1-kappa" in body


def test_register_run_appends_workflow_run_to_upstream_consumed_by(tmp_path: Path) -> None:
    (tmp_path / "entities" / "datasets").mkdir(parents=True, exist_ok=True)
    (tmp_path / "entities" / "datasets" / "up.md").write_text(
        '---\nid: "dataset:up"\ntype: "dataset"\ntitle: "Up"\norigin: "external"\n'
        'access: {level: "public", verified: true, verification_method: "retrieved", last_reviewed: "2026-04-19", source_url: "https://x"}\n'
        "consumed_by: []\n---\n",
        encoding="utf-8",
    )
    _seed_workflow_and_run(tmp_path, run_resources=[{"name": "kappa", "path": "kappa.csv", "format": "csv"}])
    _seed_resource_files(tmp_path, ["kappa"])
    runs = tmp_path / "entities" / "workflow-runs" / "wf-r1.md"
    runs.write_text(runs.read_text().replace("inputs: []", 'inputs: ["dataset:up"]'), encoding="utf-8")
    CliRunner().invoke(
        science_cli,
        ["dataset", "register-run", "workflow-run:wf-r1"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    body = (tmp_path / "entities" / "datasets" / "up.md").read_text()
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
    runs_body = (tmp_path / "entities" / "workflow-runs" / "wf-r1.md").read_text()
    assert runs_body.count("dataset:wf-r1-kappa") == 1  # produces deduplicated


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

    _append_yaml_list_item(tmp_path / "entities" / "datasets" / "wf-r1-kappa.md", "consumed_by", "plan:p1")
    runs_dir = tmp_path / "entities" / "workflow-runs"
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
    r1 = (tmp_path / "entities" / "datasets" / "wf-r1-kappa.md").read_text()
    r2 = (tmp_path / "entities" / "datasets" / "wf-r2-kappa.md").read_text()
    assert 'status: "active"' in r1
    assert 'status: "active"' in r2
    assert "plan:p1" in r1
    assert "superseded_by" not in r1
    assert "superseded_by" not in r2
