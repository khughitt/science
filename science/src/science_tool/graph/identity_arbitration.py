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
from enum import StrEnum
from typing import Any, TypeAlias

from pydantic import ValidationError
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


def _require_provenance(declaration: IdentityDeclaration) -> None:
    """A CONTRIBUTION must name where it came from.

    `IdentityDeclaration.source_ref` stays optional because non-contribution rows -- a
    cross-scope commons owner recorded for reference resolution -- legitimately have none. But a
    contribution is a source's claim, and a claim whose source cannot be named is one no reader
    can check and no author can be asked about. Guarding here lets every consumer downstream
    stop asking.
    """
    if declaration.source_ref is None:
        raise ValueError(
            f"contribution for {declaration.canonical_id!r} from adapter "
            f"{declaration.adapter!r} has no source_ref"
        )


@dataclass(frozen=True)
class EntityContribution:
    """A candidate entity offered by an owner or an external reference."""

    declaration: IdentityDeclaration
    candidate: Entity

    def __post_init__(self) -> None:
        if self.declaration.participation_mode is ParticipationMode.BORROWER:
            raise ValueError("a borrower contributes an attachment, not an entity")
        _require_provenance(self.declaration)
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
        _require_provenance(self.declaration)
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


class ArbitrationCode(StrEnum):
    """The ledger's CLOSED vocabulary.

    Closed so consumers can be total over it. A bare `str` let the strict boundary match the
    spellings it happened to remember and fall through on the rest -- and falling through means
    NOT raising, so a code nobody had considered would silently downgrade to "diagnostic" and
    the load would report success for a defect arbitration had positively found.
    """

    DUPLICATE_OWNER = "duplicate-owner"
    CONTRIBUTION_CONFLICT = "contribution-conflict"
    MISSING_OWNER = "missing-owner"
    AMBIGUOUS_REPRESENTATIVE = "ambiguous-representative"


@dataclass(frozen=True)
class ArbitrationError:
    """One issue in the ledger.

    `contributors` carries structured SourceRefs, not rendered strings: the strict loader
    boundary projects these into ContributionConflictError, and a boundary that had to parse
    display text to recover a path would make the message format load-bearing.
    """

    code: ArbitrationCode
    canonical_id: str
    owner_scope: str
    field: str
    contributors: tuple[SourceRef, ...]

    def __post_init__(self) -> None:
        if not self.contributors:
            # An error naming nobody cannot be acted on, and the strict boundary reads
            # `contributors` positionally. Empty here means a contribution reached arbitration
            # without provenance, which the contribution guards now prevent at construction.
            raise ValueError(f"arbitration error {self.code} must name the sources involved")

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
    """The permitted metadata an external candidate offers: authored, non-structural.

    Values come from the candidate ITSELF, never from its dump. A dump is a serialization: it
    turns a nested `ExternalId` into a plain dict, and the external-only path installs proposals
    with `model_copy`, which does not coerce one back. The entity would then carry dicts where
    its model declares models -- quietly, because a dict dumps identically to the model it
    impersonates. The candidate is already validated, so its attributes are the model's types.
    """
    return {
        field: getattr(candidate, field)
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
                    code=ArbitrationCode.CONTRIBUTION_CONFLICT,
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
        duplicated_scopes: set[str] = set()
        suppressed = False
        for scope in sorted(owners_by_scope):
            group = owners_by_scope[scope]
            live = [c for c in group if not c.declaration.deprecated]
            deprecated = [c for c in group if c.declaration.deprecated]
            # Only when a LIVE owner exists, i.e. only when the datapackage will not represent
            # this id. The column answers "where else do this dataset's resources live", so a
            # datapackage that represents its own id has nothing to say here -- the consumer
            # already resolves that case from the entity's own path. This is a CONSEQUENCE of
            # arbitration, never an input to it: nothing below reads it back.
            if live:
                for row in deprecated:
                    if row.declaration.adapter == "datapackage" and row.declaration.source_ref:
                        dataset_datapackages[canonical_id] = row.declaration.source_ref.path
            if len(live) >= 2:
                # Never choose. Two live owners of one identity is the identity error itself,
                # and picking one would make the defect invisible exactly where it matters.
                errors.append(
                    ArbitrationError(
                        code=ArbitrationCode.DUPLICATE_OWNER,
                        canonical_id=canonical_id,
                        owner_scope=scope,
                        field="",
                        contributors=_refs_of(live),
                    )
                )
                duplicated_scopes.add(scope)
                suppressed = True
                continue
            if live:
                representatives[scope] = live[0]
            elif deprecated:
                # A datapackage-only dataset: transitional, but it is the only owner there is.
                representatives[scope] = deprecated[0]

        for borrower in borrowers:
            scope = borrower.declaration.owner_scope
            # A DUPLICATED scope has no representative either, but "this scope owns nothing" is
            # false when it owns the id twice -- and it sends the reader off to author an owner
            # that already exists, twice. The duplicate-owner row is the actionable fact; a
            # second row contradicting it is noise in the ledger an audit reader acts on.
            if scope in representatives or scope in duplicated_scopes:
                continue
            errors.append(
                ArbitrationError(
                    code=ArbitrationCode.MISSING_OWNER,
                    canonical_id=canonical_id,
                    owner_scope=scope,
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
                        code=ArbitrationCode.AMBIGUOUS_REPRESENTATIVE,
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
            entity = _install(owner.candidate, updates)

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


def _install(candidate: Entity, updates: dict[str, Any]) -> Entity:
    """Install composed values THROUGH the model, never around it.

    An overlay speaks a DIFFERENT vocabulary than the entity model: its frontmatter is validated
    against the overlay schema, which types a date as a string. Composition is the boundary
    between the two, so it is the only place a borrower's value can be brought into the model's
    types. `model_copy(update=...)` assigns without validating, which let an overlay's
    `updated: "2026-07-10"` enter as a `str` where every consumer had been promised a `date`;
    the failure then surfaced in freshness comparing `str > date`, with nothing naming the
    overlay that caused it.

    Only the owner+borrower path needs this. External references contribute through validated
    Entity candidates, so their values are already model-typed.

    The validated payload is a THROWAWAY used to coerce, never the entity that ships. Returning
    it would rebuild the candidate from a dump, which drops private state carried from load --
    `_authored_aliases`, which the model requires be CARRIED and never inferred -- and inflates
    `model_fields_set` from what the source authored to every field the dump names. Both losses
    are silent and land far away: `build_alias_map` reads the first to tell an authored alias
    from a derived one, and `_authored_fields` reads the second to decide whom to credit.

    Installing only the coerced values keeps the shipped entity the one the owner authored,
    changed in exactly the fields composition changed.
    """
    if not updates:
        return candidate
    coerced = type(candidate).model_validate({**candidate.model_dump(), **updates})
    return candidate.model_copy(update={field: getattr(coerced, field) for field in updates})


def _refs_of(contributions: Sequence[SourceContribution]) -> tuple[SourceRef, ...]:
    """Every contribution's ref -- never a subset.

    This used to filter out ref-less contributions, which turned "a contribution had no
    provenance" into "fewer contributors than there were contributions", i.e. an error that
    under-reported who was involved and could even name nobody at all. The contribution guards
    make the ref total, so this reads it directly and a violation surfaces as a crash in the
    guard rather than a quietly shortened list.
    """
    refs = [_ref_of(c) for c in contributions]
    return tuple(sorted(refs, key=lambda ref: (ref.path, -1 if ref.line is None else ref.line, ref.adapter_name)))


def _ref_of(contribution: SourceContribution) -> SourceRef:
    ref = contribution.declaration.source_ref
    if ref is None:  # unreachable: guaranteed by _require_provenance at construction
        raise AssertionError(f"contribution for {contribution.declaration.canonical_id!r} lost its source_ref")
    return ref


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


# A whole-entity invariant (`xrefs must not contain duplicate external ids`) fails with an empty
# `loc`: it faults no single field, so no field-level vacancy can ever explain it. Naming it here
# keeps it OUT of the vacated set by construction, rather than relying on a caller to remember
# that locationless means unexplained.
_MODEL_LEVEL = "<entity>"


def _fields_the_model_rejects(entity: Entity) -> set[str]:
    """The fields on which this entity fails its OWN model contract, or an empty set.

    Arbitration must never return a representative a consumer cannot trust: the declared type is
    what every reader downstream relies on, and a node that violates it is discovered by whoever
    touches the field, far from here.

    Locationless errors are reported as `_MODEL_LEVEL`, never dropped. Filtering them turned a
    real rejection into an empty set -- which reads as "nothing wrong" -- and shipped the invalid
    entity with nothing in the ledger.
    """
    try:
        type(entity).model_validate(entity.model_dump())
    except ValidationError as error:
        return {
            str(item["loc"][0]) if item["loc"] else _MODEL_LEVEL for item in error.errors()
        }
    return set()


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
    vacated: set[str] = set()
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
                code=ArbitrationCode.CONTRIBUTION_CONFLICT,
                canonical_id=canonical_id,
                owner_scope="",
                field=field,
                contributors=_refs_of([c for c, _ in entries]),
            )
        )
        # An explicit vacancy: the disagreement is in the ledger, and no proposal won it.
        resolved[field] = None
        vacated.add(field)

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
    # NOT _install: every proposal here came from an already-validated Entity, so there is no
    # foreign vocabulary to coerce. The one non-model value this function introduces is the
    # vacancy above, which is why the result is checked rather than coerced.
    entity = first.candidate.model_copy(update=updates) if updates else first.candidate
    invalid_fields = _fields_the_model_rejects(entity)
    if invalid_fields:
        if not invalid_fields <= vacated:
            # A field the model rejects that NO conflict explains is a broken candidate reaching
            # arbitration, not a disagreement arbitration resolved. Failing here keeps the two
            # apart; swallowing it would let any invalid entity leave as a silent absence.
            raise ValueError(
                f"external-only candidate for {canonical_id!r} is invalid in fields the ledger "
                f"does not explain: {sorted(invalid_fields - vacated)}"
            )
        # A vacancy the model cannot represent: `title` is required, so "we do not know" is
        # unsayable and the choice is an invalid entity or none. None is correct -- the conflict
        # stays in the ledger naming both sources, which is the fact a reader can act on, while
        # materializing PaperEntity(title=None) would hand consumers a node that violates the
        # contract its own kind declares.
        return None, entity_fields
    return entity, entity_fields
