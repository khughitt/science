# tests/graph/test_aggregate_retire_curie_migration.py
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.aggregate_retire import apply_retirement, plan_retirement
from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\nontologies:\n  - biology\n"


def _project(root: Path, terms: list[dict], external_refs: list[dict] | None = None) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    (src / "terms.yaml").write_text(yaml.safe_dump({"terms": terms}), encoding="utf-8")
    if external_refs is not None:
        (src / "external_refs.yaml").write_text(yaml.safe_dump({"references": external_refs}), encoding="utf-8")


def _run(root: Path):
    sources = load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    plan = plan_retirement(
        root, sources, rows, promote_coined=False, delete_cruft=False, delete_shadow=False, migrate_curie_refs=True
    )
    return apply_retirement(root, plan, dry_run=False)


def _ext_refs(root: Path) -> list[dict]:
    p = root / "knowledge" / "sources" / "local" / "external_refs.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))["references"] if p.is_file() else []


def _terms(root: Path) -> list[dict]:
    p = root / "knowledge" / "sources" / "local" / "terms.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))["terms"]


def test_migrate_creates_authority_row_and_drops_aggregate_row(tmp_path: Path) -> None:
    _project(
        tmp_path,
        [
            {
                "id": "protein:BCMA",
                "title": "BCMA",
                "primary_external_id": {
                    "source": "UniProtKB",
                    "id": "Q02223",
                    "curie": "UniProtKB:Q02223",
                    "provenance": "manual",
                },
                "description": "B-cell maturation antigen.",
            }
        ],
    )
    report = _run(tmp_path)
    assert "protein:BCMA" in report.migrated
    refs = _ext_refs(tmp_path)
    assert len(refs) == 1
    assert refs[0]["id"] == "protein:BCMA"
    assert refs[0]["type"] == "protein"
    assert refs[0]["primary_external_id"] == {
        "source": "UniProtKB",
        "id": "Q02223",
        "curie": "UniProtKB:Q02223",
        "provenance": "manual",
    }
    assert refs[0]["description"] == "B-cell maturation antigen."
    assert _terms(tmp_path) == []  # aggregate row dropped


def test_migrate_is_idempotent_on_matching_curie(tmp_path: Path) -> None:
    pei = {"source": "UniProtKB", "id": "Q02223", "curie": "UniProtKB:Q02223", "provenance": "manual"}
    backed_pei = {**pei, "provenance": "prior-migration"}
    _project(
        tmp_path,
        [{"id": "protein:BCMA", "title": "BCMA", "primary_external_id": pei}],
        external_refs=[{"id": "protein:BCMA", "kind": "protein", "title": "BCMA", "primary_external_id": backed_pei}],
    )
    report = _run(tmp_path)
    assert "protein:BCMA" in report.migrated
    assert len(_ext_refs(tmp_path)) == 1  # no duplicate appended
    assert _ext_refs(tmp_path)[0]["primary_external_id"] == backed_pei  # existing authority row preserved
    assert _terms(tmp_path) == []  # aggregate row still dropped (reconciled)


def test_migrate_rejects_conflicting_curie_without_mutation(tmp_path: Path) -> None:
    _project(
        tmp_path,
        [
            {
                "id": "protein:BCMA",
                "title": "BCMA",
                "primary_external_id": {
                    "source": "UniProtKB",
                    "id": "NEW",
                    "curie": "UniProtKB:NEW",
                    "provenance": "manual",
                },
            }
        ],
        external_refs=[
            {
                "id": "protein:BCMA",
                "kind": "protein",
                "title": "BCMA",
                "primary_external_id": {
                    "source": "UniProtKB",
                    "id": "OLD",
                    "curie": "UniProtKB:OLD",
                    "provenance": "manual",
                },
            }
        ],
    )
    report = _run(tmp_path)
    assert "protein:BCMA" not in report.migrated
    assert any(cid == "protein:BCMA" and "conflict" in reason for cid, reason in report.rejected)
    assert len(_ext_refs(tmp_path)) == 1  # unchanged
    assert _ext_refs(tmp_path)[0]["primary_external_id"]["curie"] == "UniProtKB:OLD"
    assert len(_terms(tmp_path)) == 1  # aggregate row NOT dropped


def test_migrate_rejects_non_mapping_external_refs_root(tmp_path: Path) -> None:
    _project(
        tmp_path,
        [
            {
                "id": "protein:BCMA",
                "title": "BCMA",
                "primary_external_id": {
                    "source": "UniProtKB",
                    "id": "Q02223",
                    "curie": "UniProtKB:Q02223",
                    "provenance": "manual",
                },
            }
        ],
    )
    ext = tmp_path / "knowledge" / "sources" / "local" / "external_refs.yaml"
    ext.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="document root must be a mapping"):
        _run(tmp_path)
