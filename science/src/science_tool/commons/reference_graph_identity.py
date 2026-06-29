"""Pinned identity resolver over bio.reference_graph node indexes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_data_root, resolve_commons_root
from science_tool.commons.reference_graph import (
    ReferenceGraphCollectionError,
    is_reference_graph_frontmatter,
    parse_node_index_rows,
)
from science_tool.commons.reference_graph_resources import read_commons_node_rows


class ReferenceGraphIdentityError(ValueError):
    """A reference graph identity registry or node index is malformed."""


@dataclass(frozen=True, slots=True)
class ResolvedGraphMember:
    """A graph member resolved by exact key equality in one pinned registry."""

    registry_id: str
    member_key: str
    member_kind: str
    label: str
    status: str
    replaced_by: tuple[str, ...]
    dataset_usage: tuple[dict[str, Any], ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "resolution_status": "resolved",
            "registry_id": self.registry_id,
            "member_key": self.member_key,
            "member_kind": self.member_kind,
            "label": self.label,
            "status": self.status,
            "replaced_by": list(self.replaced_by),
            "dataset_usage": list(self.dataset_usage),
        }


def resolve_graph_member(
    member_key: str,
    *,
    registry_id: str,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> ResolvedGraphMember | None:
    """Resolve a non-molecular graph member identity from a pinned reference graph.

    Resolution is exact key equality within `registry_id`. Deprecated or withdrawn
    members are returned with lifecycle provenance and replacement keys surfaced;
    replacements are never followed automatically.
    """
    commons_root = commons_root or resolve_commons_root()
    data_root = data_root or resolve_commons_data_root()

    parent = CommonsEntityAdapter(commons_root).load(registry_id)
    if not is_reference_graph_frontmatter(parent.frontmatter):
        raise ReferenceGraphIdentityError(f"{registry_id} is not a bio.reference_graph dataset")

    node_rows = read_commons_node_rows(parent.frontmatter, commons_root=commons_root, data_root=data_root)
    if isinstance(node_rows, Exception):
        raise ReferenceGraphIdentityError(f"node index resource cannot be read: {node_rows}") from node_rows
    if node_rows is None:
        raise ReferenceGraphIdentityError("node index resource is unavailable")

    try:
        nodes = parse_node_index_rows(node_rows)
    except ReferenceGraphCollectionError as exc:
        raise ReferenceGraphIdentityError(f"node index is malformed: {exc}") from exc

    for node in nodes:
        if node.member_key == member_key:
            return ResolvedGraphMember(
                registry_id=registry_id,
                member_key=node.member_key,
                member_kind=node.member_kind,
                label=node.label,
                status=node.status,
                replaced_by=node.replaced_by,
                dataset_usage=node.dataset_usage,
            )
    return None
