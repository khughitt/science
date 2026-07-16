"""The identity contribution contract: what a source may contribute, and in what order.

Arbitration is a two-step discipline (identity arbitration design §3): collect the complete
candidate closure, then arbitrate it. A source contributes; it does not decide. Nothing here
selects a winner between owners -- ordering makes arbitration deterministic, and determinism
is not adjudication. Two owners of one identity is an ERROR, and an error that depends on
which adapter ran first is not an error anyone can act on.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeAlias

from science_model.entities import Entity
from science_model.entity_schema import MergePolicy
from science_model.source_ref import SourceRef

from science_tool.commons.errors import OverlayMergeError
from science_tool.commons.overlay import (
    SKIP_OVERLAY_FIELDS,
    FieldProposal,
    OverlayRecord,
    distinct_values,
    lookup_merge_policy,
    resolve_field,
)
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


@dataclass(frozen=True)
class ArbitrationError:
    """One issue in the ledger.

    `contributors` carries structured SourceRefs, not rendered strings: the strict loader
    boundary projects these into ContributionConflictError, and a boundary that had to parse
    display text to recover a path would make the message format load-bearing.
    """

    code: str
    canonical_id: str
    owner_scope: str
    field: str
    contributors: tuple[SourceRef, ...]

    @property
    def sort_key(self) -> tuple[str, str, str, str, tuple[str, ...]]:
        return (
            self.code,
            self.canonical_id,
            self.owner_scope,
            self.field,
            tuple(str(ref) for ref in self.contributors),
        )


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


def _authored_fields(candidate: Entity) -> set[str]:
    """The fields this candidate actually SPEAKS to.

    `model_dump()` yields ~67 fields for an entity that authored 12; crediting the owner for all
    of them makes provenance meaningless and, worse, reports the owner as a source of a value it
    never supplied. `model_fields_set` is what was explicitly set (including schema extensions),
    and `is_unset` removes the ones set to an absence -- owner-unset is owner-absent.
    """
    dumped = candidate.model_dump()
    return {
        field
        for field in candidate.model_fields_set
        if field in dumped and not is_unset(dumped[field])
    }


def _external_proposals(candidate: Entity) -> dict[str, Any]:
    """The permitted metadata an external candidate offers: authored, non-structural."""
    dumped = candidate.model_dump()
    return {
        field: dumped[field]
        for field in sorted(_authored_fields(candidate))
        if field not in _EXTERNAL_STRUCTURAL_FIELDS
    }


def _compose_contributions(
    *,
    canonical_id: str,
    scope: str,
    owner: EntityContribution,
    attached: list[AttachmentContribution],
    externals: list[EntityContribution],
    policies: Mapping[str, MergePolicy],
    entity_fields: dict[str, tuple[ContributionKey, ...]],
    errors: list[ArbitrationError],
) -> dict[str, Any]:
    """Resolve every proposal against the owner, one field at a time.

    Proposals are gathered from ALL contributors before any field is decided -- the two-step
    discipline at field granularity. Folding contributor-by-contributor would let the first
    borrower fill a vacancy and then fault the second for conflicting with a value the first had
    no authority to install.
    """
    authored = owner.candidate.model_dump()
    merged = dict(authored)

    proposals: dict[str, list[tuple[SourceContribution, FieldProposal]]] = defaultdict(list)
    for borrower in attached:
        for field, value in borrower.record.frontmatter.items():
            if field in SKIP_OVERLAY_FIELDS:
                continue
            proposals[field].append((borrower, FieldProposal(value=value, contests=True)))
    for external in externals:
        for field, value in _external_proposals(external.candidate).items():
            proposals[field].append((external, FieldProposal(value=value, contests=False)))

    for field in sorted(proposals):
        entries = proposals[field]
        policy = lookup_merge_policy(field, policies)
        if policy is None:
            if any(proposal.contests for _, proposal in entries):
                # Fail early: a borrower field with no policy anywhere is a broken profile, and
                # silently dropping it is how an overlay reaches nothing.
                raise OverlayMergeError(field=field, canonical_id=canonical_id)
            continue

        outcome = resolve_field(
            policy, merged.get(field), tuple(proposal for _, proposal in entries)
        )
        if outcome.conflicting:
            errors.append(
                ArbitrationError(
                    code="contribution-conflict",
                    canonical_id=canonical_id,
                    owner_scope=scope,
                    field=field,
                    contributors=_refs_of([entries[i][0] for i in outcome.conflicting]),
                )
            )
        if outcome.contributed:
            merged[field] = outcome.value
            for index in outcome.contributed:
                key = ContributionKey.from_declaration(entries[index][0].declaration)
                entity_fields[field] = entity_fields.get(field, ()) + (key,)
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
                        contributors=_refs_of(live),
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
                        contributors=_refs_of([borrower]),
                    )
                )

        if suppressed:
            continue

        entity_fields: dict[str, tuple[ContributionKey, ...]] = {}

        if representatives:
            scope = _select_scope(representatives, context.project_scope)
            if scope is None:
                # More than one scope owns this id and neither is ours nor commons. "The only
                # remaining owner" is a cardinality precondition, not licence to invent
                # precedence: choosing by adapter or path would let a name decide whose entity
                # the graph sees.
                errors.append(
                    ArbitrationError(
                        code="ambiguous-representative",
                        canonical_id=canonical_id,
                        owner_scope="",
                        field="",
                        contributors=_refs_of(
                            [representatives[s] for s in sorted(representatives)]
                        ),
                    )
                )
                continue
            owner = representatives[scope]
            owner_key = ContributionKey.from_declaration(owner.declaration)
            entity_source_adapters[canonical_id] = owner.declaration.adapter

            authored = owner.candidate.model_dump()
            for field in _authored_fields(owner.candidate):
                entity_fields[field] = (owner_key,)

            attached = [b for b in borrowers if b.declaration.owner_scope == scope]
            for borrower in attached:
                if borrower.declaration.source_ref:
                    overlay_paths[canonical_id] = borrower.declaration.source_ref.path
            if attached:
                # Fail early: a borrower composed under no policy contributes nothing and says
                # nothing. Absent policy is a broken caller, not a quiet no-op.
                policies = context.field_policies[(scope, canonical_id)]
            else:
                policies = context.field_policies.get((scope, canonical_id), {})

            merged = _compose_contributions(
                canonical_id=canonical_id,
                scope=scope,
                owner=owner,
                attached=attached,
                externals=externals,
                policies=policies,
                entity_fields=entity_fields,
                errors=errors,
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
            entity, entity_fields = _materialize_external_only(
                canonical_id=canonical_id,
                externals=externals,
                entity_source_adapters=entity_source_adapters,
                errors=errors,
            )
            if entity is None:
                continue
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
        errors=tuple(sorted(errors, key=lambda error: error.sort_key)),
    )


def _refs_of(contributions: Sequence[SourceContribution]) -> tuple[SourceRef, ...]:
    refs = [c.declaration.source_ref for c in contributions if c.declaration.source_ref]
    return tuple(sorted(refs, key=lambda ref: (ref.path, -1 if ref.line is None else ref.line, ref.adapter_name)))


def _select_scope(
    representatives: Mapping[str, EntityContribution], project_scope: str
) -> str | None:
    """The B3a materialization rule. None when it does not determine a single scope.

    This picks an in-memory representative; it does not resolve identity. Every owner row
    survives, so cross-scope ambiguity stays visible to the resolver.
    """
    if project_scope in representatives:
        return project_scope
    if COMMONS_SCOPE in representatives:
        return COMMONS_SCOPE
    if len(representatives) == 1:
        return next(iter(representatives))
    return None


def _materialize_external_only(
    *,
    canonical_id: str,
    externals: list[EntityContribution],
    entity_source_adapters: dict[str, str],
    errors: list[ArbitrationError],
) -> tuple[Entity | None, dict[str, tuple[ContributionKey, ...]]]:
    """Materialize a node no source owns, so references to it resolve.

    No owner means no policy, so the only rule left is agreement. Sequences union in key order --
    sequence IS the value, so ordering them decides nothing. Scalars must agree: where externals
    disagree the field is ledgered and left VACANT, because the first candidate is a proposal
    like any other, and letting its value stand would make bib line order the authority on an
    entity's DOI.
    """
    entity_fields: dict[str, tuple[ContributionKey, ...]] = {}
    first = externals[0]
    entity_source_adapters[canonical_id] = first.declaration.adapter

    proposals: dict[str, list[tuple[EntityContribution, Any]]] = defaultdict(list)
    for external in externals:
        for field, value in _external_proposals(external.candidate).items():
            proposals[field].append((external, value))

    authored = first.candidate.model_dump()
    resolved: dict[str, Any] = {}
    for field in sorted(proposals):
        entries = proposals[field]
        keys = tuple(ContributionKey.from_declaration(c.declaration) for c, _ in entries)
        values = [value for _, value in entries]

        if all(isinstance(value, list) for value in values):
            merged_list: list[Any] = []
            for value in values:
                for item in value:
                    if item not in merged_list:
                        merged_list.append(item)
            resolved[field] = merged_list
            entity_fields[field] = keys
            continue

        distinct = distinct_values(values)
        if len(distinct) == 1:
            resolved[field] = distinct[0]
            entity_fields[field] = keys
            continue
        errors.append(
            ArbitrationError(
                code="contribution-conflict",
                canonical_id=canonical_id,
                owner_scope="",
                field=field,
                contributors=_refs_of([c for c, _ in entries]),
            )
        )
        # An explicit vacancy: the disagreement is in the ledger, and no proposal won it.
        resolved[field] = None

    for field in _authored_fields(first.candidate):
        if field not in resolved:
            entity_fields.setdefault(
                field, (ContributionKey.from_declaration(first.declaration),)
            )
    updates = {
        field: value
        for field, value in resolved.items()
        if field not in authored or authored[field] != value
    }
    entity = first.candidate.model_copy(update=updates) if updates else first.candidate
    return entity, entity_fields
