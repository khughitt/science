"""Virtual payload resolver for bio.reference_graph.member datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.adapter import CommonsEntityRecord
from science_tool.commons.member import MemberOf
from science_tool.commons.member_payload import MemberPayloadError, UnresolvedMemberPayloadError
from science_tool.commons.reference_graph import (
    ReferenceGraphCollectionError,
    ReferenceGraphEdge,
    ReferenceGraphNode,
    parse_edge_rows,
    parse_node_index_rows,
)
from science_tool.commons.reference_graph_resources import read_commons_edge_rows, read_commons_node_rows


@dataclass(frozen=True, slots=True)
class ReferenceGraphMemberPayload:
    node: ReferenceGraphNode
    incident_edges: tuple[ReferenceGraphEdge, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": {
                "member_key": self.node.member_key,
                "member_kind": self.node.member_kind,
                "label": self.node.label,
                "status": self.node.status,
                "replaced_by": list(self.node.replaced_by),
                "dataset_usage": list(self.node.dataset_usage),
            },
            "incident_edges": [
                {
                    "subject": edge.subject,
                    "predicate": edge.predicate,
                    "object": edge.object,
                    "evidence": edge.evidence,
                    "dataset_usage": list(edge.dataset_usage),
                }
                for edge in self.incident_edges
            ],
        }


def resolve_reference_graph_member_payload(
    *,
    parent: CommonsEntityRecord,
    member_of: MemberOf,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> ReferenceGraphMemberPayload:
    node_rows = read_commons_node_rows(parent.frontmatter, commons_root=commons_root, data_root=data_root)
    if isinstance(node_rows, Exception):
        raise MemberPayloadError(f"node index resource cannot be read: {node_rows}") from node_rows
    if node_rows is None:
        raise MemberPayloadError("node index resource is unavailable")

    try:
        nodes = parse_node_index_rows(node_rows)
    except ReferenceGraphCollectionError as exc:
        raise MemberPayloadError(f"node index is malformed: {exc}") from exc

    nodes_by_key = {node.member_key: node for node in nodes}
    member_key = member_of.member_key
    node = nodes_by_key.get(member_key)
    if node is None:
        raise UnresolvedMemberPayloadError(f"member_key {member_key!r} is absent from {parent.canonical_id}")

    edge_rows = read_commons_edge_rows(parent.frontmatter, commons_root=commons_root, data_root=data_root)
    if isinstance(edge_rows, Exception):
        raise MemberPayloadError(f"edge resource cannot be read: {edge_rows}") from edge_rows
    if edge_rows is None:
        return ReferenceGraphMemberPayload(node=node, incident_edges=())

    try:
        edges = parse_edge_rows(edge_rows)
    except ReferenceGraphCollectionError as exc:
        raise MemberPayloadError(f"edge resource is malformed: {exc}") from exc

    incident_edges = tuple(edge for edge in edges if edge.subject == member_key or edge.object == member_key)
    return ReferenceGraphMemberPayload(node=node, incident_edges=incident_edges)
