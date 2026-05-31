from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from science_tool.commons.member_payload import (
    UnsupportedMemberPayloadError,
    VirtualMemberPayload,
    resolve_virtual_member_payload,
)


def _write_dataset(root: Path, slug: str, frontmatter: str) -> None:
    dataset_dir = root / "datasets" / slug
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "entity.md").write_text(f"---\n{frontmatter}---\n\nbody\n", encoding="utf-8")
    (dataset_dir / "datapackage.yaml").write_text(
        "name: test-package\nresources: []\n",
        encoding="utf-8",
    )


def _base_dataset_frontmatter(
    *,
    slug: str,
    title: str,
    schema_profile: str = "science-entity-base/1.0+dataset/1.0",
    origin: str = "external",
    datapackage: str = "datapackage.yaml",
    extra: str = "",
) -> str:
    text = (
        f'schema_profile: "{schema_profile}"\n'
        f'id: "dataset:{slug}"\n'
        'type: "dataset"\n'
        f'title: "{title}"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-31"\n'
        'updated: "2026-05-31"\n'
        f'datapackage: "{datapackage}"\n'
        f'origin: "{origin}"\n'
        'tier: "use-now"\n'
    )
    if origin == "external":
        text += (
            "access:\n"
            '  level: "public"\n'
            "  verified: true\n"
            '  source_url: "https://example.org/data"\n'
        )
    return text + extra


def _write_member(
    root: Path,
    *,
    slug: str = "member",
    parent_dataset: str = "dataset:parent",
    member_key: str = "member-1",
) -> None:
    _write_dataset(
        root,
        slug,
        _base_dataset_frontmatter(
            slug=slug,
            title="Promoted member",
            origin="derived",
            datapackage="virtual:member-of",
            extra=(
                f'parent_dataset: "{parent_dataset}"\n'
                "derivation:\n"
                "  kind: member_of\n"
                f'  parent_dataset: "{parent_dataset}"\n'
                f'  member_key: "{member_key}"\n'
            ),
        ),
    )


def test_resolve_virtual_member_payload_returns_none_for_non_member(tmp_path: Path) -> None:
    commons_root = tmp_path / "commons"
    _write_dataset(
        commons_root,
        "parent",
        _base_dataset_frontmatter(slug="parent", title="Ordinary dataset"),
    )

    assert resolve_virtual_member_payload("dataset:parent", commons_root=commons_root, data_root=tmp_path / "data") is None


def test_resolve_virtual_member_payload_rejects_unsupported_parent_collection(tmp_path: Path) -> None:
    commons_root = tmp_path / "commons"
    _write_dataset(
        commons_root,
        "parent",
        _base_dataset_frontmatter(slug="parent", title="Ordinary parent"),
    )
    _write_member(commons_root)

    with pytest.raises(UnsupportedMemberPayloadError, match="unsupported parent collection profile"):
        resolve_virtual_member_payload("dataset:member", commons_root=commons_root, data_root=tmp_path / "data")


def test_resolve_virtual_member_payload_detects_geneset_parent_as_explicit_d2_followup(tmp_path: Path) -> None:
    commons_root = tmp_path / "commons"
    _write_dataset(
        commons_root,
        "parent",
        _base_dataset_frontmatter(
            slug="parent",
            title="Gene set collection",
            schema_profile="science-entity-base/1.0+dataset/1.0+bio.geneset/1.0",
            extra=(
                'source_class: "reference"\n'
                'member_key_column: "set_key"\n'
                'members_resource: "sets"\n'
                "n_sets: 1\n"
                "set_size_summary:\n"
                "  min: 2\n"
                "  median: 2\n"
                "  max: 2\n"
                "identifier_space:\n"
                '  tier: "gene"\n'
                '  namespace: "hgnc_id"\n'
                '  resolution_status: "declared_unresolved"\n'
            ),
        ),
    )
    _write_member(commons_root)

    with pytest.raises(UnsupportedMemberPayloadError, match="bio.geneset virtual payload resolution is reserved for D2"):
        resolve_virtual_member_payload("dataset:member", commons_root=commons_root, data_root=tmp_path / "data")


def test_virtual_member_payload_dataclass_is_generic_container() -> None:
    payload: dict[str, Any] = {"node": {"id": "MONDO:0005148"}}

    container = VirtualMemberPayload(
        member_id="dataset:mondo-member",
        parent_dataset="dataset:mondo",
        parent_slug="mondo",
        member_key="MONDO:0005148",
        payload_kind="bio.reference_graph.member",
        payload=payload,
    )

    assert container.payload is payload
    assert container.parent_slug == "mondo"
