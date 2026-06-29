"""Reference-collection member primitives (RCM-D2/D5).

Pure helpers shared by every reference-collection instance (assembly registry,
gene-set collection, crosswalks). No network, no bio. See
docs/plans/historical/2026-05-26-reference-collection-member-promotion-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root

_VALID_DECLARED_STATUS = frozenset({"resolved", "declared_unresolved"})


@dataclass(frozen=True, slots=True)
class MemberOf:
    """The parsed `derivation.kind: member_of` block (RCM-D5)."""

    parent_dataset: str
    member_key: str


class ResolutionState(str, Enum):
    """Outcome of evaluating a keyed reference against its collection (RCM-D2)."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    DECLARED_UNRESOLVED = "declared_unresolved"
    UNKNOWN = "unknown"


def parse_member_of(entity: dict[str, Any]) -> MemberOf | None:
    """Return the MemberOf block if `entity` is a promoted member, else None.

    Trusts schema validation for shape; this only extracts. Returns None for a
    workflow derivation, a missing derivation, or a derivation whose `kind` is
    not `member_of`.
    """
    derivation = entity.get("derivation")
    if not isinstance(derivation, dict) or derivation.get("kind") != "member_of":
        return None
    return MemberOf(
        parent_dataset=derivation["parent_dataset"],
        member_key=derivation["member_key"],
    )


def evaluate_key_resolution(
    *,
    key: str,
    available_keys: set[str] | None,
    declared_status: str | None,
) -> ResolutionState:
    """Evaluate a keyed reference against its collection (guardrail 1, RCM-D2).

    - `declared_status == "declared_unresolved"` → DECLARED_UNRESOLVED (a
      first-class, honoured state; never an error).
    - else if `available_keys` is known → RESOLVED iff `key` is present, else
      UNRESOLVED.
    - else (no index, no declaration) → UNKNOWN; the caller decides severity.

    `declared_status` must be one of {"resolved", "declared_unresolved"} or None.

    Note: `declared_status == "resolved"` is accepted (it is a valid authored
    `resolution_status`) but is NOT an authoritative override — resolution is
    still decided by `available_keys`. A dataset cannot bypass key-index
    verification by declaring itself resolved; if its key is absent the result
    is UNRESOLVED.
    """
    if declared_status is not None and declared_status not in _VALID_DECLARED_STATUS:
        raise ValueError(
            f"resolution_status must be one of {sorted(_VALID_DECLARED_STATUS)} or absent; got {declared_status!r}"
        )
    if declared_status == "declared_unresolved":
        return ResolutionState.DECLARED_UNRESOLVED
    if available_keys is not None:
        return ResolutionState.RESOLVED if key in available_keys else ResolutionState.UNRESOLVED
    return ResolutionState.UNKNOWN


@dataclass(frozen=True, slots=True)
class ResolvedMember:
    """A promoted member resolved to its parent collection + key (RCM-D5).

    Byte-level slicing of the parent on `member_key` is the consumer's job; this
    only resolves the delegation target.
    """

    member_id: str
    parent_dataset: str
    parent_slug: str
    member_key: str


def resolve_member(member_id: str, *, commons_root: Path | None = None) -> ResolvedMember | None:
    """Resolve a promoted member to its parent collection and key.

    Returns None if `member_id` is not a `member_of` dataset. Raises a
    CommonsError (via the adapter) if the member entity, or its declared parent
    collection, is not present in the commons.
    """
    commons_root = commons_root or resolve_commons_root()
    adapter = CommonsEntityAdapter(commons_root)

    member_record = adapter.load(member_id)  # raises if the member entity is absent
    member_of = parse_member_of(member_record.frontmatter)
    if member_of is None:
        return None

    parent_record = adapter.load(member_of.parent_dataset)  # raises if absent
    return ResolvedMember(
        member_id=member_id,
        parent_dataset=member_of.parent_dataset,
        parent_slug=parent_record.slug,
        member_key=member_of.member_key,
    )
