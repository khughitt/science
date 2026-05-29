from __future__ import annotations

from pathlib import Path

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
    (root / "science.yaml").write_text("profile: research\n", encoding="utf-8")


def _write_geneset_datapackage(root: Path, *, resource_path: str) -> Path:
    dp_dir = root / "data" / "reactome"
    dp_dir.mkdir(parents=True)
    dp_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "id": "dataset:reactome-v89",
                "type": "dataset",
                "title": "Reactome v89",
                "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.geneset/1.0",
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
                "resources": [{"name": "sets", "path": resource_path}],
            }
        ),
        encoding="utf-8",
    )
    return dp_dir


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
