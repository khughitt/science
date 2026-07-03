from __future__ import annotations

from pathlib import Path

import yaml
from science_model.packages.schema import IdentityContext

from science_tool.commons.datapackage import parse_canonical_datapackage_yaml, render_canonical_datapackage_yaml
from science_tool.commons.identity_stamp import derive_stamp, stamp_agrees
from science_tool.datasets_register import write_per_output_datapackages


def _identity_context() -> dict:
    return {
        "taxon": 9606,
        "assembly": {
            "seqcol_digest": "g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp",
            "registry": "dataset:assembly-registry",
            "resolution_status": "resolved",
        },
        "molecular_ids": {
            "gene": {
                "namespace": "hgnc_id",
                "registry": "dataset:hgnc",
                "resolution_status": "resolved",
                "transform": {
                    "type": "symbol_remap",
                    "from": "hgnc_symbol",
                    "method": "approved_symbol",
                    "dataset": "dataset:hgnc-symbol-remap",
                },
            }
        },
    }


def test_derive_stamp_preserves_aliases_and_returns_independent_copy() -> None:
    entity_identity = IdentityContext.model_validate(_identity_context())

    stamp = derive_stamp(entity_identity)

    assert stamp == _identity_context()
    assert stamp["molecular_ids"]["gene"]["transform"]["from"] == "hgnc_symbol"
    assert "from_" not in stamp["molecular_ids"]["gene"]["transform"]

    stamp["molecular_ids"]["gene"]["namespace"] = "ensembl_gene_id"
    assert entity_identity.molecular_ids["gene"].namespace == "hgnc_id"


def test_derive_stamp_copies_raw_dict_identity() -> None:
    raw = _identity_context()

    stamp = derive_stamp(raw)

    assert stamp == raw
    stamp["assembly"]["seqcol_digest"] = "mutated"
    assert raw["assembly"]["seqcol_digest"] == "g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp"


def test_stamp_agrees_fails_for_mutated_present_stamp() -> None:
    identity = _identity_context()
    datapackage = {"science": {"identity_context": derive_stamp(identity)}}
    datapackage["science"]["identity_context"]["taxon"] = 10090

    assert not stamp_agrees(identity, datapackage)


def test_stamp_agrees_skips_absent_stamp() -> None:
    assert stamp_agrees(_identity_context(), {"resources": []})


def test_render_canonical_datapackage_preserves_science_identity_context_and_strips_mm30() -> None:
    valid_hash = "sha256:" + "a" * 64
    yaml_text = render_canonical_datapackage_yaml(
        project_doc={
            "name": "project-ds",
            "mm30": {"external_source": "local"},
            "science": {
                "identity_context": _identity_context(),
                "note": "project-owned metadata should stay inside science",
            },
            "resources": [{"name": "r1", "path": "r1.txt"}],
        },
        canonical_slug="canonical-ds",
        per_resource={"r1": (valid_hash, 12)},
    )

    parsed = parse_canonical_datapackage_yaml(yaml_text)

    assert "mm30" not in parsed
    assert parsed["science"]["identity_context"] == _identity_context()
    assert parsed["science"]["note"] == "project-owned metadata should stay inside science"


def test_write_per_output_datapackages_stamps_output_identity(tmp_path: Path) -> None:
    (tmp_path / "entities" / "workflows").mkdir(parents=True)
    workflow_fm = yaml.safe_dump(
        {
            "id": "workflow:wf",
            "type": "workflow",
            "title": "WF",
            "outputs": [
                {
                    "slug": "expression",
                    "title": "Expression",
                    "resource_names": ["expr"],
                    "identity": _identity_context(),
                }
            ],
        },
        sort_keys=False,
    )
    (tmp_path / "entities" / "workflows" / "wf.md").write_text(f"---\n{workflow_fm}---\n", encoding="utf-8")
    (tmp_path / "entities" / "workflow-runs").mkdir(parents=True)
    run_fm = yaml.safe_dump(
        {
            "id": "workflow-run:wf-r1",
            "type": "workflow-run",
            "title": "WF r1",
            "workflow": "workflow:wf",
        },
        sort_keys=False,
    )
    (tmp_path / "entities" / "workflow-runs" / "wf-r1.md").write_text(f"---\n{run_fm}---\n", encoding="utf-8")
    run_dir = tmp_path / "results" / "wf" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "expr.csv").write_text("gene,value\nA,1\n", encoding="utf-8")
    (run_dir / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-runtime-1.0"],
                "name": "wf-r1",
                "resources": [{"name": "expr", "path": "expr.csv", "format": "csv"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    written = write_per_output_datapackages(tmp_path, "workflow-run:wf-r1")

    assert written == [run_dir / "expression" / "datapackage.yaml"]
    datapackage = yaml.safe_load(written[0].read_text(encoding="utf-8"))
    assert datapackage["science"]["identity_context"] == _identity_context()
