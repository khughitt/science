from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.validate.checks.genesets import check_genesets
from science_tool.validate.checks.genesets import evaluate_geneset_collections
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result
from science_tool.validate.result import Severity


_GENE_REGISTRY = "dataset:gene-crosswalk-hgnc"
_VALID_GENE_META = {
    "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0",
    "member_key_column": "gene_key",
}
_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)


def _geneset(**extra: object) -> dict[str, object]:
    return {
        "id": "dataset:reactome-v89",
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.geneset/1.0",
        "_path": "data/reactome/datapackage.yaml",
        "source_class": "reference",
        "member_key_column": "set_key",
        "members_resource": "sets",
        "n_sets": 1,
        "set_size_summary": {"min": 2, "median": 2, "max": 2},
        "identifier_space": {
            "tier": "gene",
            "namespace": "hgnc_id",
            "registry": _GENE_REGISTRY,
            "resolution_status": "resolved",
        },
        **extra,
    }


def _row(**extra: object) -> dict[str, object]:
    return {"set_key": "R-HSA-1", "name": "Cell cycle", "member_ids": "HGNC:1;HGNC:2", **extra}


def _rules(results: list[Result]) -> list[str]:
    return [r.rule for r in results]


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_project(root: Path) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (root / "knowledge" / "local").mkdir(parents=True)


def _write_geneset_datapackage(root: Path, *, resource_path: str, n_sets: int = 1) -> Path:
    dp_dir = root / "data" / "reactome"
    dp_dir.mkdir(parents=True)
    dp_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "id": "dataset:reactome-v89",
                "type": "dataset",
                "title": "Reactome v89",
                "status": "active",
                "origin": "external",
                "tier": "use-now",
                "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.geneset/1.0",
                "source_class": "reference",
                "access": {"level": "public", "verified": True},
                "member_key_column": "set_key",
                "members_resource": "sets",
                "n_sets": n_sets,
                "set_size_summary": {"min": 2, "median": 2, "max": 2},
                "identifier_space": {
                    "tier": "gene",
                    "namespace": "hgnc_id",
                    "registry": _GENE_REGISTRY,
                    "resolution_status": "resolved",
                },
                "resources": [{"name": "sets", "path": resource_path}],
            }
        ),
        encoding="utf-8",
    )
    return dp_dir


def _write_geneset_dataset(root: Path, *, rows: str, n_sets: int = 1) -> None:
    dp_dir = _write_geneset_datapackage(root, resource_path="sets.csv", n_sets=n_sets)
    dp_dir.joinpath("sets.csv").write_text(rows, encoding="utf-8")


def _write_gene_crosswalk_dataset(root: Path) -> None:
    dp_dir = root / "data" / "gene-crosswalk"
    dp_dir.mkdir(parents=True)
    dp_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "id": _GENE_REGISTRY,
                "type": "dataset",
                "title": "HGNC crosswalk",
                "status": "active",
                "origin": "external",
                "tier": "use-now",
                "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0",
                "source_class": "reference",
                "access": {"level": "public", "verified": True},
                "member_key_column": "gene_key",
                "resources": [{"name": "crosswalk", "path": "crosswalk.csv"}],
            }
        ),
        encoding="utf-8",
    )


def _write_gene_crosswalk_commons(root: Path) -> Path:
    commons = root / "commons"
    dataset_dir = commons / "datasets" / "gene-crosswalk-hgnc"
    dataset_dir.mkdir(parents=True)
    dataset_dir.joinpath("entity.md").write_text(
        """\
---
schema_profile: "science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0"
id: "dataset:gene-crosswalk-hgnc"
type: "dataset"
title: "HGNC crosswalk"
version: "1.0.0"
status: "active"
created: "2026-05-28"
updated: "2026-05-28"
datapackage: "datapackage.yaml"
origin: "external"
tier: "use-now"
source_class: "reference"
access:
  level: "public"
  verified: true
member_key_column: "gene_key"
---

# HGNC crosswalk
""",
        encoding="utf-8",
    )
    dataset_dir.joinpath("datapackage.yaml").write_text(
        """\
name: gene-crosswalk-hgnc
profile: "data-package"
resources:
  - name: crosswalk
    path: crosswalk.csv
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 0
""",
        encoding="utf-8",
    )
    return commons


def _empty_commons(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    commons = root / "empty-commons"
    commons.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))


def test_valid_geneset_collection_passes_silently() -> None:
    results = list(
        evaluate_geneset_collections(
            [_geneset()],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={_GENE_REGISTRY: _VALID_GENE_META},
        )
    )
    assert results == []


def test_malformed_collection_errors() -> None:
    fm = _geneset(member_key_column="pathway_id")
    results = list(
        evaluate_geneset_collections(
            [fm],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={_GENE_REGISTRY: _VALID_GENE_META},
        )
    )
    assert _rules(results) == ["geneset.collection-malformed"]
    assert results[0].severity is Severity.ERROR


def test_boolean_numeric_collection_fields_are_malformed() -> None:
    fm = _geneset(
        n_sets=True,
        set_size_summary={"min": True, "median": True, "max": True},
    )
    results = list(
        evaluate_geneset_collections(
            [fm],
            rows_by_dataset_id={"dataset:reactome-v89": [{"set_key": "R-HSA-1", "name": "One", "member_ids": "HGNC:1"}]},
            registry_meta_by_id={_GENE_REGISTRY: _VALID_GENE_META},
        )
    )
    assert _rules(results) == ["geneset.collection-malformed"]


def test_float_min_max_collection_fields_are_malformed_before_row_read() -> None:
    fm = _geneset(set_size_summary={"min": 1.1, "median": 1.1, "max": 1.1})
    results = list(
        evaluate_geneset_collections(
            [fm],
            rows_by_dataset_id={},
            registry_meta_by_id={},
        )
    )
    assert _rules(results) == ["geneset.collection-malformed"]


def test_n_sets_mismatch_errors() -> None:
    fm = _geneset(n_sets=2)
    results = list(
        evaluate_geneset_collections(
            [fm],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={_GENE_REGISTRY: _VALID_GENE_META},
        )
    )
    assert _rules(results) == ["geneset.n-sets-mismatch"]


def test_set_size_summary_mismatch_errors() -> None:
    fm = _geneset(set_size_summary={"min": 1, "median": 1, "max": 1})
    results = list(
        evaluate_geneset_collections(
            [fm],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={_GENE_REGISTRY: _VALID_GENE_META},
        )
    )
    assert _rules(results) == ["geneset.set-size-summary-mismatch"]


def test_unsupported_identifier_namespace_errors() -> None:
    fm = _geneset(identifier_space={"tier": "gene", "namespace": "refseq"})
    results = list(
        evaluate_geneset_collections(
            [fm],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={_GENE_REGISTRY: _VALID_GENE_META},
        )
    )
    assert _rules(results) == ["geneset.identifier-namespace-unsupported"]


def test_unavailable_registry_infos() -> None:
    results = list(
        evaluate_geneset_collections(
            [_geneset()],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={_GENE_REGISTRY: None},
        )
    )
    assert _rules(results) == ["geneset.identifier-registry-unavailable"]
    assert results[0].severity is Severity.INFO


def test_declared_unresolved_infos_and_skips_registry_validation() -> None:
    fm = _geneset(
        identifier_space={"tier": "gene", "namespace": "hgnc_id", "resolution_status": "declared_unresolved"}
    )
    results = list(
        evaluate_geneset_collections(
            [fm],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={},
        )
    )
    assert _rules(results) == ["geneset.identifier-declared-unresolved"]
    assert results[0].severity is Severity.INFO


def test_check_genesets_rejects_unsafe_member_resource_path(tmp_path: Path) -> None:
    _write_project(tmp_path)
    _write_geneset_datapackage(tmp_path, resource_path="../outside.csv")

    results = list(check_genesets(_ctx(tmp_path)))

    assert _rules(results) == ["geneset.members-resource-malformed"]
    assert results[0].severity is Severity.ERROR


def test_check_genesets_reports_malformed_member_resource_bytes(tmp_path: Path) -> None:
    _write_project(tmp_path)
    dp_dir = _write_geneset_datapackage(tmp_path, resource_path="sets.csv")
    dp_dir.joinpath("sets.csv").write_bytes(b"\xff\xfe\x00")

    results = list(check_genesets(_ctx(tmp_path)))

    assert _rules(results) == ["geneset.members-resource-malformed"]
    assert results[0].severity is Severity.ERROR


def test_check_genesets_reads_local_members_resource(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_project(tmp_path)
    _empty_commons(tmp_path, monkeypatch)
    _write_gene_crosswalk_dataset(tmp_path)
    _write_geneset_dataset(
        tmp_path,
        rows="set_key,name,member_ids,dataset_usage,source_pmids\n"
        'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:study-a"",""role"":""set_definition_source""}]",12345\n',
    )

    results = list(check_genesets(_ctx(tmp_path)))

    assert results == []


def test_check_genesets_resolves_identifier_registry_from_commons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_project(tmp_path)
    commons = _write_gene_crosswalk_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    _write_geneset_dataset(
        tmp_path,
        rows="set_key,name,member_ids,dataset_usage,source_pmids\n"
        'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:study-a"",""role"":""training""}]",12345\n',
    )

    results = list(check_genesets(_ctx(tmp_path)))

    assert results == []


def test_check_genesets_reports_malformed_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_project(tmp_path)
    _empty_commons(tmp_path, monkeypatch)
    _write_gene_crosswalk_dataset(tmp_path)
    _write_geneset_dataset(tmp_path, rows="set_key,name,member_ids\nR-HSA-1,Cell cycle,\n")

    results = list(check_genesets(_ctx(tmp_path)))

    assert _rules(results) == ["geneset.members-resource-malformed"]
    assert results[0].severity is Severity.ERROR


def test_check_genesets_unbuilt_members_resource_infos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_project(tmp_path)
    _empty_commons(tmp_path, monkeypatch)
    _write_gene_crosswalk_dataset(tmp_path)
    _write_geneset_dataset(tmp_path, rows="set_key,name,member_ids\nR-HSA-1,Cell cycle,HGNC:1;HGNC:2\n")
    tmp_path.joinpath("data", "reactome", "sets.csv").unlink()

    results = list(check_genesets(_ctx(tmp_path)))

    assert _rules(results) == ["geneset.members-resource-unavailable"]
    assert results[0].severity is Severity.INFO
