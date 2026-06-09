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
from typing import Protocol

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

    @property
    def is_genuine(self) -> bool:
        """True when >=2 owner rows are non-deprecated — the genuine §B1 duplicate the
        compiler must reject. A collision involving a transitional deprecated owner (an
        entities.yaml aggregate stub §C3, or a synthesized orphan-datapackage owner §B4)
        shadowing a real owner is carried as rollout debt (§C4), surfaced as a non-blocking
        WARN, not a hard error. The single source of truth for this grade across the
        validate check, the graph audit, and the migrator.
        """
        return sum(1 for row in self.rows if not row.deprecated) >= 2


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

    def owner_scopes_by_id(self) -> dict[str, frozenset[str]]:
        """canonical_id -> the owner scopes that own it across all loaded scopes.

        Derived from owner rows only (borrowers/external-refs do not own). Used by
        the reference resolver to detect a bare id owned in >1 loaded scope
        (design §B3a) and to enumerate valid scope-prefix names.
        """
        grouped: dict[str, set[str]] = defaultdict(set)
        for scope, cid in self.owners():
            grouped[cid].add(scope)
        return {cid: frozenset(scopes) for cid, scopes in grouped.items()}

    def collisions(self) -> list[IdentityCollision]:
        """Every (owner_scope, canonical_id) claimed by more than one owner row."""
        return [
            IdentityCollision(owner_scope=scope, canonical_id=cid, rows=tuple(rows))
            for (scope, cid), rows in self.owners().items()
            if len(rows) > 1
        ]


_COMMONS_SCOPE = "commons"


def classify_owner_scope(adapter: str, *, project_name: str) -> tuple[str, bool]:
    """Return (owner_scope, deprecated) for an owner declaration from `adapter`.

    Fails loud on an empty adapter (review: missing provenance must not silently
    become a project markdown owner).
    """
    if not adapter:
        raise ValueError("identity declaration requires a non-empty adapter name")
    if adapter == "commons-merged":
        return (_COMMONS_SCOPE, False)
    if adapter == "bib":
        # External-reference authority scope (design §B3): bib rows are never
        # owners, so this scope only labels provenance; it is non-deprecated.
        return ("bib", False)
    if adapter == "curie-ref":
        # External-reference authority scope (design §B3, Phase 4c): curie rows are
        # never owners; this scope labels provenance and is non-deprecated.
        return ("curie-ref", False)
    # aggregate (entities.yaml) and datapackage are transitional deprecated owners:
    # the target substrate retires entities.yaml (§B5) and treats datapackages as
    # attachments, not owners (§B4). Flag them so later phases can find them.
    if adapter in ("aggregate", "datapackage"):
        return (project_name, True)
    return (project_name, False)


class _DeclaredSources(Protocol):
    identity_declarations: list[IdentityDeclaration]


def build_identity_table(sources: _DeclaredSources) -> IdentityTable:
    """Compile the IdentityTable from a project's collected declarations (§C1)."""
    return IdentityTable(rows=list(sources.identity_declarations))
