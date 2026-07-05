# tests/graph/test_curie_ref_adapter.py
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.storage_adapters.curie_ref import CurieRefAdapter

_REL = "knowledge/sources/local/external_refs.yaml"


def _write(root: Path, refs: list[dict]) -> None:
    p = root / "knowledge" / "sources" / "local"
    p.mkdir(parents=True, exist_ok=True)
    (p / "external_refs.yaml").write_text(yaml.safe_dump({"references": refs}), encoding="utf-8")


def test_discover_one_ref_per_row_and_load_raw_shape(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [
            {
                "id": "protein:BCMA",
                "kind": "protein",
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
    adapter = CurieRefAdapter(local_profile="local")
    refs = adapter.discover(tmp_path)
    assert len(refs) == 1
    assert refs[0].adapter_name == "curie-ref"
    assert refs[0].path == _REL
    raw = adapter.load_raw(refs[0])
    assert raw["kind"] == "protein"
    assert raw["id"] == "protein:BCMA"
    assert raw["title"] == "BCMA"
    assert raw["same_as"] == ["UniProtKB:Q02223"]  # LIST, not frozenset
    assert raw["file_path"] == _REL
    assert raw["primary_external_id"] == {
        "source": "UniProtKB",
        "id": "Q02223",
        "curie": "UniProtKB:Q02223",
        "provenance": "manual",
    }


def test_participation_mode_is_external_reference() -> None:
    assert CurieRefAdapter(local_profile="local").participation_mode is ParticipationMode.EXTERNAL_REFERENCE


def test_title_defaults_to_id_when_absent(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [
            {
                "id": "gene:MYC",
                "kind": "gene",
                "primary_external_id": {"source": "HGNC", "id": "7553", "curie": "HGNC:7553", "provenance": "manual"},
            }
        ],
    )
    adapter = CurieRefAdapter(local_profile="local")
    raw = adapter.load_raw(adapter.discover(tmp_path)[0])
    assert raw["title"] == "gene:MYC"


def test_duplicate_id_raises(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [
            {
                "id": "protein:BCMA",
                "kind": "protein",
                "primary_external_id": {
                    "source": "UniProtKB",
                    "id": "Q02223",
                    "curie": "UniProtKB:Q02223",
                    "provenance": "manual",
                },
            },
            {
                "id": "protein:BCMA",
                "kind": "protein",
                "primary_external_id": {
                    "source": "UniProt",
                    "id": "OTHER",
                    "curie": "UniProt:OTHER",
                    "provenance": "manual",
                },
            },
        ],
    )
    with pytest.raises(ValueError, match="duplicate"):
        CurieRefAdapter(local_profile="local").discover(tmp_path)


def test_malformed_primary_external_id_raises(tmp_path: Path) -> None:
    # Missing id, curie, provenance — ExternalId requires all four, and external_refs.yaml
    # is the durable authority, so discover() fails loud rather than skipping the row.
    _write(tmp_path, [{"id": "protein:X", "kind": "protein", "primary_external_id": {"source": "UniProt"}}])
    with pytest.raises(ValueError, match="primary_external_id"):
        CurieRefAdapter(local_profile="local").discover(tmp_path)


def test_load_raw_before_discover_raises(tmp_path: Path) -> None:
    from science_model.source_ref import SourceRef

    adapter = CurieRefAdapter(local_profile="local")
    with pytest.raises(RuntimeError, match="discover"):
        adapter.load_raw(SourceRef(adapter_name="curie-ref", path=_REL, line=0))


def test_missing_file_yields_no_refs(tmp_path: Path) -> None:
    (tmp_path / "knowledge" / "sources" / "local").mkdir(parents=True)
    assert CurieRefAdapter(local_profile="local").discover(tmp_path) == []


def test_absent_references_key_yields_no_refs(tmp_path: Path) -> None:
    # File exists but declares no `references:` key at all -> empty authority, not an error.
    p = tmp_path / "knowledge" / "sources" / "local"
    p.mkdir(parents=True)
    (p / "external_refs.yaml").write_text("other: 1\n", encoding="utf-8")
    assert CurieRefAdapter(local_profile="local").discover(tmp_path) == []


def test_non_list_references_raises(tmp_path: Path) -> None:
    # A present-but-non-list `references` (here a mapping) must fail loud, NOT be
    # silently coerced to an empty authority (durable-authority contract).
    p = tmp_path / "knowledge" / "sources" / "local"
    p.mkdir(parents=True)
    (p / "external_refs.yaml").write_text("references: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a list"):
        CurieRefAdapter(local_profile="local").discover(tmp_path)


def test_non_mapping_document_root_raises(tmp_path: Path) -> None:
    # A malformed document root (e.g. a YAML list) must fail loud. Only an empty file
    # or an absent `references` key means "empty authority".
    p = tmp_path / "knowledge" / "sources" / "local"
    p.mkdir(parents=True)
    (p / "external_refs.yaml").write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a mapping"):
        CurieRefAdapter(local_profile="local").discover(tmp_path)
