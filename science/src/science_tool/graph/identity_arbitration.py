"""The identity contribution contract: what a source may contribute, and in what order.

Arbitration is a two-step discipline (identity arbitration design §3): collect the complete
candidate closure, then arbitrate it. A source contributes; it does not decide. Nothing here
selects a winner between owners -- ordering makes arbitration deterministic, and determinism
is not adjudication. Two owners of one identity is an ERROR, and an error that depends on
which adapter ran first is not an error anyone can act on.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, TypeAlias

from science_model.entities import Entity
from science_model.entity_schema import MergePolicy

from science_tool.commons.overlay import OverlayRecord, compose_frontmatter
from science_tool.graph.identity_table import (
    COMMONS_SCOPE,
    IdentityDeclaration,
    ParticipationMode,
)
from science_tool.unset import is_unset

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


@dataclass(frozen=True)
class ArbitrationContext:
    """What arbitration needs from the caller, and nothing it could re-derive itself."""

    project_scope: str
    field_policies: Mapping[tuple[str, str], Mapping[str, MergePolicy]]


@dataclass(frozen=True, order=True)
class ArbitrationError:
    """One issue in the ledger. Ordered, so the ledger is a set, not a sequence of events."""

    code: str
    canonical_id: str
    owner_scope: str
    field: str
    contributors: tuple[str, ...]


@dataclass(frozen=True)
class ArbitrationResult:
    entities: tuple[Entity, ...]
    identity_declarations: tuple[IdentityDeclaration, ...]
    entity_source_adapters: dict[str, str]
    dataset_datapackages: dict[str, str]
    overlay_paths: dict[str, str]
    field_sources: dict[str, dict[str, tuple[ContributionKey, ...]]]
    errors: tuple[ArbitrationError, ...]


# An external reference SUPPORTS a node; it never restates what identity the node has. These
# fields are structural: a bib entry's notion of `kind` or `project` is an artifact of how it was
# parsed, not a claim about the entity, so they are never offered as updates.
_EXTERNAL_STRUCTURAL_FIELDS = frozenset(
    {"id", "canonical_id", "kind", "project", "file_path", "profile", "schema_profile"}
)


def _contribution_ordering(contribution: SourceContribution) -> tuple[int, str, str, int]:
    return ContributionKey.from_declaration(contribution.declaration).ordering


def arbitrate_contributions(
    contributions: Iterable[SourceContribution],
    *,
    context: ArbitrationContext,
) -> ArbitrationResult:
    """Arbitrate a COMPLETE candidate closure into entities, provenance, and an issue ledger.

    The caller collects; this decides. Nothing here reads disk, and no contribution is mutated,
    so the same closure yields the same result in any encounter order -- the property the whole
    design turns on.
    """
    ordered = tuple(sorted(contributions, key=_contribution_ordering))
    return _arbitrate_ordered(ordered, context=context)


def _reject_indistinguishable(
    contributions: list[SourceContribution],
) -> list[SourceContribution]:
    """Collapse identical contributions; refuse differing ones that share a key.

    Uniqueness is per entity, NOT global: an aggregate file owns many entities from one path with
    no line, and those share every key component legitimately. Within ONE entity, though, two
    differing contributions at one key are indistinguishable to every consumer, so a stable sort
    would silently resolve them by adapter run order.
    """
    kept: dict[ContributionKey, SourceContribution] = {}
    for contribution in contributions:
        key = ContributionKey.from_declaration(contribution.declaration)
        existing = kept.get(key)
        if existing is None:
            kept[key] = contribution
        elif existing != contribution:
            raise ValueError(
                f"indistinguishable contributions for {contribution.declaration.canonical_id!r}: "
                f"two differing records share {key}. Nothing downstream can order them."
            )
    return list(kept.values())


def _offer_external_fields(
    base: dict[str, Any],
    candidate: Entity,
    policies: Mapping[str, MergePolicy],
    key: ContributionKey,
    field_sources: dict[str, tuple[ContributionKey, ...]],
) -> dict[str, Any]:
    """Merge an external candidate's PERMITTED metadata onto `base`.

    Unlike a borrower, an external reference is not project input and cannot contest the owner:
    a defended REPLACE field is simply not offered. Offering it as an error would make every bib
    entry that names an owned paper a build failure.
    """
    merged = dict(base)
    for field, value in candidate.model_dump().items():
        if field in _EXTERNAL_STRUCTURAL_FIELDS or is_unset(value):
            continue
        policy = policies.get(field)
        if policy is MergePolicy.APPEND:
            combined = list(merged.get(field) or []) + list(value)
            deduped: list[Any] = []
            for item in combined:
                if item not in deduped:
                    deduped.append(item)
            if deduped != merged.get(field):
                merged[field] = deduped
                field_sources[field] = field_sources.get(field, ()) + (key,)
        elif policy is MergePolicy.REPLACE and is_unset(merged.get(field)):
            merged[field] = value
            field_sources[field] = field_sources.get(field, ()) + (key,)
    return merged


def _merge_supporting_external(
    base: dict[str, Any],
    candidate: Entity,
    key: ContributionKey,
    field_sources: dict[str, tuple[ContributionKey, ...]],
) -> dict[str, Any]:
    """Merge one external onto another when NO owner exists: non-conflicting metadata only.

    With no owner there is no policy to consult, so the only safe rule is to fill vacancies.
    Two externals disagreeing on a set field are left as the first one said -- an unowned node is
    not the place to adjudicate between citations.
    """
    merged = dict(base)
    for field, value in candidate.model_dump().items():
        if field in _EXTERNAL_STRUCTURAL_FIELDS or is_unset(value):
            continue
        if is_unset(merged.get(field)):
            merged[field] = value
            field_sources[field] = field_sources.get(field, ()) + (key,)
    return merged


def _arbitrate_ordered(
    ordered: tuple[SourceContribution, ...],
    *,
    context: ArbitrationContext,
) -> ArbitrationResult:
    entities: list[Entity] = []
    declarations: list[IdentityDeclaration] = []
    entity_source_adapters: dict[str, str] = {}
    dataset_datapackages: dict[str, str] = {}
    overlay_paths: dict[str, str] = {}
    field_sources: dict[str, dict[str, tuple[ContributionKey, ...]]] = {}
    errors: list[ArbitrationError] = []

    by_id: dict[str, list[SourceContribution]] = defaultdict(list)
    for contribution in ordered:
        by_id[contribution.declaration.canonical_id].append(contribution)

    for canonical_id in sorted(by_id):
        contributions = _reject_indistinguishable(by_id[canonical_id])
        declarations.extend(c.declaration for c in contributions)

        owners = [
            c
            for c in contributions
            if isinstance(c, EntityContribution)
            and c.declaration.participation_mode is ParticipationMode.OWNER
        ]
        borrowers = [c for c in contributions if isinstance(c, AttachmentContribution)]
        externals = [
            c
            for c in contributions
            if isinstance(c, EntityContribution)
            and c.declaration.participation_mode is ParticipationMode.EXTERNAL_REFERENCE
        ]

        owners_by_scope: dict[str, list[EntityContribution]] = defaultdict(list)
        for owner in owners:
            owners_by_scope[owner.declaration.owner_scope].append(owner)

        representatives: dict[str, EntityContribution] = {}
        suppressed = False
        for scope in sorted(owners_by_scope):
            group = owners_by_scope[scope]
            live = [c for c in group if not c.declaration.deprecated]
            deprecated = [c for c in group if c.declaration.deprecated]
            for row in deprecated:
                if row.declaration.adapter == "datapackage" and row.declaration.source_ref:
                    dataset_datapackages[canonical_id] = row.declaration.source_ref.path
            if len(live) >= 2:
                # Never choose. Two live owners of one identity is the identity error itself,
                # and picking one would make the defect invisible exactly where it matters.
                errors.append(
                    ArbitrationError(
                        code="duplicate-owner",
                        canonical_id=canonical_id,
                        owner_scope=scope,
                        field="",
                        contributors=tuple(
                            sorted(str(c.declaration.source_ref) for c in live)
                        ),
                    )
                )
                suppressed = True
                continue
            if live:
                representatives[scope] = live[0]
            elif deprecated:
                # A datapackage-only dataset: transitional, but it is the only owner there is.
                representatives[scope] = deprecated[0]

        for borrower in borrowers:
            if borrower.declaration.owner_scope not in representatives:
                errors.append(
                    ArbitrationError(
                        code="missing-owner",
                        canonical_id=canonical_id,
                        owner_scope=borrower.declaration.owner_scope,
                        field="",
                        contributors=(str(borrower.declaration.source_ref),),
                    )
                )

        if suppressed:
            continue

        entity_fields: dict[str, tuple[ContributionKey, ...]] = {}

        if representatives:
            # The B3a materialization rule: prefer this project's owner, then commons, then the
            # only one left. The rows keep every scope, so cross-scope ambiguity stays visible to
            # the resolver -- this picks an in-memory representative, it does not resolve identity.
            if context.project_scope in representatives:
                scope = context.project_scope
            elif COMMONS_SCOPE in representatives:
                scope = COMMONS_SCOPE
            else:
                scope = min(
                    representatives,
                    key=lambda s: _contribution_ordering(representatives[s]),
                )
            owner = representatives[scope]
            owner_key = ContributionKey.from_declaration(owner.declaration)
            entity_source_adapters[canonical_id] = owner.declaration.adapter

            authored = owner.candidate.model_dump()
            merged = dict(authored)
            for field in merged:
                entity_fields[field] = (owner_key,)

            attached = [b for b in borrowers if b.declaration.owner_scope == scope]
            if attached:
                # Fail early: a borrower composed under no policy contributes nothing and says
                # nothing. Absent policy is a broken caller, not a quiet no-op.
                policies = context.field_policies[(scope, canonical_id)]
            else:
                policies = context.field_policies.get((scope, canonical_id), {})

            for borrower in attached:
                key = ContributionKey.from_declaration(borrower.declaration)
                if borrower.declaration.source_ref:
                    overlay_paths[canonical_id] = borrower.declaration.source_ref.path
                composition = compose_frontmatter(
                    merged,
                    borrower.record.frontmatter,
                    policies,
                    canonical_id=canonical_id,
                )
                for conflict in composition.conflicts:
                    errors.append(
                        ArbitrationError(
                            code="contribution-conflict",
                            canonical_id=canonical_id,
                            owner_scope=scope,
                            field=conflict.field,
                            contributors=(str(borrower.declaration.source_ref),),
                        )
                    )
                for field, source in composition.field_sources.items():
                    if source in ("overlay", "canonical+overlay"):
                        entity_fields[field] = entity_fields.get(field, ()) + (key,)
                merged = composition.frontmatter

            for external in externals:
                merged = _offer_external_fields(
                    merged,
                    external.candidate,
                    policies,
                    ContributionKey.from_declaration(external.declaration),
                    entity_fields,
                )

            # Only what actually CHANGED, so an untouched field keeps the owner's own value
            # object rather than a round-tripped copy of it.
            updates = {
                field: value
                for field, value in merged.items()
                if field not in authored or authored[field] != value
            }
            entity = owner.candidate.model_copy(update=updates) if updates else owner.candidate

        elif externals:
            # No owner: an external-only node materializes so references resolve, without any
            # source becoming its owner. The identity rows still say EXTERNAL_REFERENCE.
            first = externals[0]
            first_key = ContributionKey.from_declaration(first.declaration)
            entity_source_adapters[canonical_id] = first.declaration.adapter
            authored = first.candidate.model_dump()
            merged = dict(authored)
            for field in merged:
                entity_fields[field] = (first_key,)
            for external in externals[1:]:
                merged = _merge_supporting_external(
                    merged,
                    external.candidate,
                    ContributionKey.from_declaration(external.declaration),
                    entity_fields,
                )
            updates = {
                field: value
                for field, value in merged.items()
                if field not in authored or authored[field] != value
            }
            entity = first.candidate.model_copy(update=updates) if updates else first.candidate
        else:
            continue

        entities.append(entity)
        field_sources[canonical_id] = entity_fields

    declarations.sort(
        key=lambda row: (
            ContributionKey.from_declaration(row).ordering,
            row.canonical_id,
        )
    )
    return ArbitrationResult(
        entities=tuple(sorted(entities, key=lambda e: e.canonical_id)),
        identity_declarations=tuple(declarations),
        entity_source_adapters=entity_source_adapters,
        dataset_datapackages=dataset_datapackages,
        overlay_paths=overlay_paths,
        field_sources=field_sources,
        errors=tuple(sorted(errors)),
    )
