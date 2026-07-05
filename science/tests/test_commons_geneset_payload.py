from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from science_tool.commons.member_payload import (
    MemberPayloadError,
    UnresolvedMemberPayloadError,
    VirtualMemberPayload,
    resolve_virtual_member_payload,
)


def _hash(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _csv_bytes(rows: list[dict[str, str]], fieldnames: list[str]) -> bytes:
    import io

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _dataset_usage(ref: str) -> str:
    return json.dumps([{"ref": ref, "role": "set_definition_source", "overlap": "full"}])


def _write_entity(dataset_dir: Path, frontmatter: dict[str, Any]) -> None:
    dataset_dir.mkdir(parents=True)
    dataset_dir.joinpath("entity.md").write_text(
        "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n\nbody\n",
        encoding="utf-8",
    )


def _write_geneset_commons(
    tmp_path: Path,
    *,
    member_key: str = "R-HSA-1",
    write_members_file: bool = True,
) -> tuple[Path, Path]:
    commons_root = tmp_path / "commons"
    data_root = tmp_path / "data"
    parent_dir = commons_root / "datasets" / "reactome-v89"
    member_dir = commons_root / "datasets" / "reactome-r-hsa-1"
    data_dir = data_root / "reactome-v89"
    data_dir.mkdir(parents=True)

    member_rows = [
        {
            "set_key": "R-HSA-1",
            "name": "Cell cycle",
            "member_ids": "HGNC:1;HGNC:2",
            "source_class": "reference",
            "derived_kind": "",
            "dataset_usage": _dataset_usage("dataset:study-a"),
            "source_pmids": "12345;67890",
        },
        {
            "set_key": "R-HSA-2",
            "name": "Metabolism",
            "member_ids": "HGNC:3",
            "source_class": "",
            "derived_kind": "",
            "dataset_usage": "[]",
            "source_pmids": "",
        },
    ]
    member_bytes = _csv_bytes(
        member_rows,
        [
            "set_key",
            "name",
            "member_ids",
            "source_class",
            "derived_kind",
            "dataset_usage",
            "source_pmids",
        ],
    )
    if write_members_file:
        data_dir.joinpath("sets.csv").write_bytes(member_bytes)

    identifier_space = {
        "tier": "gene",
        "namespace": "hgnc_id",
        "registry": "dataset:gene-crosswalk-hgnc",
        "resolution_status": "resolved",
    }
    _write_entity(
        parent_dir,
        {
            "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.geneset/1.0",
            "id": "dataset:reactome-v89",
            "kind": "dataset",
            "title": "Reactome v89",
            "version": "1.0.0",
            "status": "active",
            "created": "2026-05-28",
            "updated": "2026-05-28",
            "datapackage": "datapackage.yaml",
            "origin": "external",
            "tier": "use-now",
            "source_class": "reference",
            "access": {"level": "public", "availability": "available", "verified": True},
            "member_key_column": "set_key",
            "members_resource": "sets",
            "n_sets": 2,
            "set_size_summary": {"min": 1, "median": 1.5, "max": 2},
            "identifier_space": identifier_space,
        },
    )
    parent_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "reactome-v89",
                "resources": [{"name": "sets", "path": "sets.csv", "hash": _hash(member_bytes)}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    _write_entity(
        member_dir,
        {
            "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.geneset.member/1.0",
            "id": "dataset:reactome-r-hsa-1",
            "kind": "dataset",
            "title": "R-HSA-1",
            "version": "1.0.0",
            "status": "active",
            "created": "2026-05-28",
            "updated": "2026-05-28",
            "datapackage": "virtual:member-of",
            "origin": "derived",
            "tier": "use-now",
            "source_class": "reference",
            "parent_dataset": "dataset:reactome-v89",
            "derivation": {
                "kind": "member_of",
                "parent_dataset": "dataset:reactome-v89",
                "member_key": member_key,
            },
            "identifier_space": identifier_space,
            "n_members": 2,
        },
    )
    member_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump({"name": "reactome-r-hsa-1", "resources": []}, sort_keys=False),
        encoding="utf-8",
    )

    return commons_root, data_root


def _replace_member_bytes(commons_root: Path, data_root: Path, *, content: bytes) -> None:
    data_root.joinpath("reactome-v89", "sets.csv").write_bytes(content)
    datapackage_path = commons_root / "datasets" / "reactome-v89" / "datapackage.yaml"
    datapackage = yaml.safe_load(datapackage_path.read_text(encoding="utf-8"))
    datapackage["resources"][0]["hash"] = _hash(content)
    datapackage_path.write_text(yaml.safe_dump(datapackage, sort_keys=False), encoding="utf-8")


@pytest.fixture(autouse=True)
def _hermetic_commons_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SCIENCE_COMMONS_ROOT", raising=False)
    monkeypatch.delenv("SCIENCE_COMMONS_DATA_ROOT", raising=False)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "config"))


def test_resolve_virtual_geneset_member_payload_returns_matching_member_row(tmp_path: Path) -> None:
    commons_root, data_root = _write_geneset_commons(tmp_path)

    payload = resolve_virtual_member_payload(
        "dataset:reactome-r-hsa-1",
        commons_root=commons_root,
        data_root=data_root,
    )

    assert isinstance(payload, VirtualMemberPayload)
    assert payload.payload_kind == "bio.geneset.member"
    assert payload.member_key == "R-HSA-1"
    assert payload.payload["identifier_space"] == {
        "tier": "gene",
        "namespace": "hgnc_id",
        "registry": "dataset:gene-crosswalk-hgnc",
        "resolution_status": "resolved",
    }
    assert payload.payload["row"] == {
        "set_key": "R-HSA-1",
        "name": "Cell cycle",
        "member_ids": ["HGNC:1", "HGNC:2"],
        "n_members": 2,
        "source_class": "reference",
        "derived_kind": None,
        "dataset_usage": [{"ref": "dataset:study-a", "role": "set_definition_source", "overlap": "full"}],
        "source_pmids": ["12345", "67890"],
    }


def test_resolve_geneset_member_payload_rejects_missing_members_file(tmp_path: Path) -> None:
    commons_root, data_root = _write_geneset_commons(tmp_path, write_members_file=False)

    with pytest.raises(MemberPayloadError, match="members resource cannot be read"):
        resolve_virtual_member_payload(
            "dataset:reactome-r-hsa-1",
            commons_root=commons_root,
            data_root=data_root,
        )


def test_resolve_geneset_member_payload_rejects_malformed_members_csv(tmp_path: Path) -> None:
    commons_root, data_root = _write_geneset_commons(tmp_path)
    malformed = b"set_key,name\nR-HSA-1,Cell cycle\n"
    _replace_member_bytes(commons_root, data_root, content=malformed)

    with pytest.raises(MemberPayloadError, match="members resource is malformed"):
        resolve_virtual_member_payload(
            "dataset:reactome-r-hsa-1",
            commons_root=commons_root,
            data_root=data_root,
        )


def test_resolve_geneset_member_payload_rejects_absent_member_key(tmp_path: Path) -> None:
    commons_root, data_root = _write_geneset_commons(tmp_path, member_key="R-HSA-404")

    with pytest.raises(UnresolvedMemberPayloadError, match="R-HSA-404"):
        resolve_virtual_member_payload(
            "dataset:reactome-r-hsa-1",
            commons_root=commons_root,
            data_root=data_root,
        )
