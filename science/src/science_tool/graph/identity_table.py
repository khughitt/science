"""Compiled identity table: every entity's participation mode and owner scope.

Built from row-based declarations collected inside ``load_project_sources`` at
emit time (the compiler output the substrate design, §C1, requires consumers to
read instead of re-walking disk). This module defines the value types and the
collision rule; the loader populates the declarations.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

from science_model.source_ref import SourceRef


class ParticipationMode(str, Enum):
    """What a single identity row contributes (design §B3)."""

    OWNER = "owner"
    BORROWER = "borrower"
    EXTERNAL_REFERENCE = "external-reference"


@dataclass(frozen=True)
class IdentityDeclaration:
    """One identity row: an entity's participation in one owner scope."""

    canonical_id: str
    participation_mode: ParticipationMode
    owner_scope: str
    adapter: str
    source_ref: SourceRef | None
    deprecated: bool = False  # transitional owner (e.g. aggregate), design §C3


@dataclass(frozen=True)
class IdentityCollision:
    """Two owner rows sharing one (owner_scope, canonical_id) — the identity error."""

    owner_scope: str
    canonical_id: str
    rows: tuple[IdentityDeclaration, ...]


@dataclass(frozen=True)
class IdentityTable:
    """All identity declarations compiled from a project's loaded sources."""

    rows: list[IdentityDeclaration] = field(default_factory=list)

    def owners(self) -> dict[tuple[str, str], list[IdentityDeclaration]]:
        """Owner rows grouped by the identity key (owner_scope, canonical_id)."""
        grouped: dict[tuple[str, str], list[IdentityDeclaration]] = defaultdict(list)
        for row in self.rows:
            if row.participation_mode is ParticipationMode.OWNER:
                grouped[(row.owner_scope, row.canonical_id)].append(row)
        return dict(grouped)

    def collisions(self) -> list[IdentityCollision]:
        """Every (owner_scope, canonical_id) claimed by more than one owner row."""
        return [
            IdentityCollision(owner_scope=scope, canonical_id=cid, rows=tuple(rows))
            for (scope, cid), rows in self.owners().items()
            if len(rows) > 1
        ]
