"""The identity contribution contract: what a source may contribute, and in what order.

Arbitration is a two-step discipline (identity arbitration design §3): collect the complete
candidate closure, then arbitrate it. A source contributes; it does not decide. Nothing here
selects a winner between owners -- ordering makes arbitration deterministic, and determinism
is not adjudication. Two owners of one identity is an ERROR, and an error that depends on
which adapter ran first is not an error anyone can act on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from science_model.entities import Entity

from science_tool.commons.overlay import OverlayRecord
from science_tool.graph.identity_table import IdentityDeclaration, ParticipationMode

# Total over ParticipationMode by construction: the module fails at import if a mode is
# added without a rank, rather than raising KeyError inside a sort on real data.
_ROLE_RANK: dict[ParticipationMode, int] = {
    ParticipationMode.OWNER: 0,
    ParticipationMode.BORROWER: 1,
    ParticipationMode.EXTERNAL_REFERENCE: 2,
}

_UNRANKED = set(ParticipationMode) - set(_ROLE_RANK)
if _UNRANKED:  # pragma: no cover - import-time totality guard
    raise RuntimeError(f"participation modes lack a contribution rank: {sorted(_UNRANKED)}")


@dataclass(frozen=True)
class EntityContribution:
    """A candidate entity offered by an owner or an external reference."""

    declaration: IdentityDeclaration
    candidate: Entity

    def __post_init__(self) -> None:
        if self.declaration.participation_mode is ParticipationMode.BORROWER:
            raise ValueError("a borrower contributes an attachment, not an entity")
        if self.declaration.canonical_id != self.candidate.canonical_id:
            raise ValueError(
                "identity declaration and entity candidate disagree on canonical_id: "
                f"{self.declaration.canonical_id!r} != {self.candidate.canonical_id!r}"
            )


@dataclass(frozen=True)
class AttachmentContribution:
    """An overlay a borrower attaches to an entity it does not own."""

    declaration: IdentityDeclaration
    record: OverlayRecord

    def __post_init__(self) -> None:
        if self.declaration.participation_mode is not ParticipationMode.BORROWER:
            raise ValueError("only a borrower contributes an attachment")
        if self.declaration.canonical_id != self.record.canonical_id:
            raise ValueError(
                "identity declaration and overlay attachment disagree on canonical_id: "
                f"{self.declaration.canonical_id!r} != {self.record.canonical_id!r}"
            )


SourceContribution: TypeAlias = EntityContribution | AttachmentContribution


@dataclass(frozen=True)
class ContributionKey:
    """A total order over contributions. Orders; does not adjudicate."""

    role: ParticipationMode
    authority: str
    path: str
    position: int

    @classmethod
    def from_declaration(cls, declaration: IdentityDeclaration) -> ContributionKey:
        ref = declaration.source_ref
        return cls(
            role=declaration.participation_mode,
            authority=f"{declaration.owner_scope}:{declaration.adapter}",
            path="" if ref is None else ref.path,
            position=-1 if ref is None or ref.line is None else ref.line,
        )

    @property
    def ordering(self) -> tuple[int, str, str, int]:
        return (_ROLE_RANK[self.role], self.authority, self.path, self.position)


def is_unset(value: object) -> bool:
    """True when `value` is ABSENT, as a shape -- never as truthiness.

    `False`, `0`, and `0.0` are values an author wrote and an owner defends. Reading absence
    off truthiness (`if not value:`) silently reclassifies them as missing and lets a borrower
    overwrite an authored `False`, which is exactly the defect the superseded helper carried.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return len(value) == 0
    return False
