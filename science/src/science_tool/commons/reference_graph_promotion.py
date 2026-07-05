"""Scaffold promoted bio.reference_graph.member datasets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_data_root, resolve_commons_root
from science_tool.commons.member import MemberOf
from science_tool.commons.reference_graph import is_reference_graph_frontmatter
from science_tool.commons.reference_graph_payload import resolve_reference_graph_member_payload

_DATASET_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


@dataclass(frozen=True, slots=True)
class ReferenceGraphMemberScaffold:
    canonical_id: str
    entity_path: Path
    datapackage_path: Path
    frontmatter: dict[str, Any]
    applied: bool

    def to_json(self, *, commons_root: Path) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "canonical_id": self.canonical_id,
            "entity_path": str(self.entity_path.relative_to(commons_root)),
            "datapackage_path": str(self.datapackage_path.relative_to(commons_root)),
            "frontmatter": self.frontmatter,
        }


def scaffold_reference_graph_member(
    *,
    parent_dataset: str,
    member_key: str,
    slug: str,
    stamp: date | None = None,
    title: str | None = None,
    tier: str = "use-now",
    apply: bool = False,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> ReferenceGraphMemberScaffold:
    """Plan or write a promoted child dataset for one reference-graph member."""
    if not _DATASET_SLUG_RE.fullmatch(slug):
        raise ValueError("slug must match dataset slug syntax: [a-z0-9][a-z0-9-]{1,63}")
    stamp = stamp or date.today()
    commons_root = commons_root or resolve_commons_root()
    data_root = data_root or resolve_commons_data_root()

    adapter = CommonsEntityAdapter(commons_root)
    parent = adapter.load(parent_dataset)
    if not is_reference_graph_frontmatter(parent.frontmatter):
        raise ValueError(f"{parent_dataset} is not a bio.reference_graph dataset")

    member_of = MemberOf(parent_dataset=parent_dataset, member_key=member_key)
    payload = resolve_reference_graph_member_payload(
        parent=parent,
        member_of=member_of,
        commons_root=commons_root,
        data_root=data_root,
    )
    node = payload.node

    canonical_id = f"dataset:{slug}"
    member_dir = commons_root / "datasets" / slug
    entity_path = member_dir / "entity.md"
    datapackage_path = member_dir / "datapackage.yaml"
    frontmatter: dict[str, Any] = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0",
        "id": canonical_id,
        "kind": "dataset",
        "title": title or node.label,
        "version": "1.0.0",
        "status": node.status,
        "created": stamp.isoformat(),
        "updated": stamp.isoformat(),
        "origin": "derived",
        "tier": tier,
        "source_class": "reference",
        "parent_dataset": parent_dataset,
        "datapackage": "virtual:member-of",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": parent_dataset,
            "member_key": member_key,
        },
        "member_kind": node.member_kind,
        "label": node.label,
    }
    if node.replaced_by:
        frontmatter["replaced_by"] = list(node.replaced_by)
    if node.dataset_usage:
        frontmatter["dataset_usage"] = list(node.dataset_usage)

    if apply:
        if member_dir.exists():
            raise FileExistsError(f"{member_dir}: target dataset directory already exists")
        member_dir.mkdir(parents=True)
        entity_path.write_text(_render_entity(frontmatter), encoding="utf-8")
        datapackage_path.write_text("resources: []\n", encoding="utf-8")
        adapter.load(canonical_id)

    return ReferenceGraphMemberScaffold(
        canonical_id=canonical_id,
        entity_path=entity_path,
        datapackage_path=datapackage_path,
        frontmatter=frontmatter,
        applied=apply,
    )


def _render_entity(frontmatter: dict[str, Any]) -> str:
    rendered = yaml.safe_dump(frontmatter, sort_keys=False)
    return f"---\n{rendered}---\n"
