"""Virtual-member payload dispatch for promoted commons datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.adapter import CommonsEntityAdapter, CommonsEntityRecord
from science_tool.commons.config import resolve_commons_data_root, resolve_commons_root
from science_tool.commons.geneset import is_geneset_frontmatter
from science_tool.commons.member import parse_member_of
from science_tool.commons.reference_graph import is_reference_graph_frontmatter


class MemberPayloadError(ValueError):
    """Base error for virtual-member payload resolution failures."""


class UnsupportedMemberPayloadError(MemberPayloadError):
    """Raised when a parent collection profile has no payload resolver."""


class UnresolvedMemberPayloadError(MemberPayloadError):
    """Raised when a supported resolver cannot resolve the requested member."""


@dataclass(frozen=True, slots=True)
class VirtualMemberPayload:
    member_id: str
    parent_dataset: str
    parent_slug: str
    member_key: str
    payload_kind: str
    payload: dict[str, Any]


def resolve_virtual_member_payload(
    member_id: str,
    *,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> VirtualMemberPayload | None:
    """Resolve a promoted member dataset into its profile-specific virtual payload."""
    if commons_root is None:
        commons_root = resolve_commons_root()
    if data_root is None:
        data_root = resolve_commons_data_root()

    adapter = CommonsEntityAdapter(commons_root)
    member = adapter.load(member_id)
    member_of = parse_member_of(member.frontmatter)
    if member_of is None:
        return None

    parent = adapter.load(member_of.parent_dataset)
    if is_reference_graph_frontmatter(parent.frontmatter):
        from science_tool.commons.reference_graph_payload import (
            resolve_reference_graph_member_payload,
        )

        graph_payload = resolve_reference_graph_member_payload(
            parent=parent,
            member_of=member_of,
            commons_root=commons_root,
            data_root=data_root,
        )
        return VirtualMemberPayload(
            member_id=member_id,
            parent_dataset=member_of.parent_dataset,
            parent_slug=parent.slug,
            member_key=member_of.member_key,
            payload_kind="bio.reference_graph.member",
            payload=graph_payload.to_dict(),
        )

    raise UnsupportedMemberPayloadError(_unsupported_message(parent))


def _unsupported_message(parent: CommonsEntityRecord) -> str:
    if is_geneset_frontmatter(parent.frontmatter):
        return "bio.geneset virtual payload resolution is reserved for D2"
    return (
        "unsupported parent collection profile for "
        f"{parent.canonical_id}: {parent.schema_profile}"
    )
