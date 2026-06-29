"""Virtual payload resolver for bio.geneset.member datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.adapter import CommonsEntityRecord
from science_tool.commons.geneset import GenesetCollectionError, GenesetRow, parse_geneset_rows
from science_tool.commons.geneset_resources import read_commons_member_rows
from science_tool.commons.member import MemberOf
from science_tool.commons.member_payload import MemberPayloadError, UnresolvedMemberPayloadError


@dataclass(frozen=True, slots=True)
class GenesetMemberPayload:
    row: GenesetRow
    identifier_space: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "identifier_space": dict(self.identifier_space),
            "row": {
                "set_key": self.row.set_key,
                "name": self.row.name,
                "member_ids": list(self.row.member_ids),
                "n_members": self.row.n_members,
                "source_class": self.row.source_class,
                "derived_kind": self.row.derived_kind,
                "dataset_usage": list(self.row.dataset_usage),
                "source_pmids": list(self.row.source_pmids),
            },
        }


def resolve_geneset_member_payload(
    *,
    parent: CommonsEntityRecord,
    member_of: MemberOf,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> GenesetMemberPayload:
    raw_rows = read_commons_member_rows(parent.frontmatter, commons_root=commons_root, data_root=data_root)
    if isinstance(raw_rows, Exception):
        raise MemberPayloadError(f"members resource cannot be read: {raw_rows}") from raw_rows
    if raw_rows is None:
        raise MemberPayloadError("members resource is unavailable")

    try:
        rows = parse_geneset_rows(raw_rows)
    except GenesetCollectionError as exc:
        raise MemberPayloadError(f"members resource is malformed: {exc}") from exc

    row_by_key = {row.set_key: row for row in rows}
    member_key = member_of.member_key
    row = row_by_key.get(member_key)
    if row is None:
        raise UnresolvedMemberPayloadError(f"member_key {member_key!r} is absent from {parent.canonical_id}")

    identifier_space = parent.frontmatter.get("identifier_space")
    if not isinstance(identifier_space, dict):
        raise MemberPayloadError("parent geneset identifier_space is unavailable")

    return GenesetMemberPayload(row=row, identifier_space=identifier_space)
