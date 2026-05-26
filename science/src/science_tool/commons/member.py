"""Reference-collection member primitives (RCM-D2/D5).

Pure helpers shared by every reference-collection instance (assembly registry,
gene-set collection, crosswalks). No network, no bio. See
docs/plans/2026-05-26-reference-collection-member-promotion-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

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
            f"resolution_status must be one of {sorted(_VALID_DECLARED_STATUS)} or absent; "
            f"got {declared_status!r}"
        )
    if declared_status == "declared_unresolved":
        return ResolutionState.DECLARED_UNRESOLVED
    if available_keys is not None:
        return ResolutionState.RESOLVED if key in available_keys else ResolutionState.UNRESOLVED
    return ResolutionState.UNKNOWN
