"""Per-kind vocabulary declared by the shipped entity profiles.

The Kind Descriptor (`science_model.profiles.EntityKind`) is the sole SSOT for
what a kind is called, where it lives, and which statuses it may carry. This
module holds the lookup tables derived from the shipped profiles and nothing
else, so it imports `science_model` only.

That import floor is the point. `science_tool.entities` reaches the graph and
commons packages, so anything imported *from inside* those packages cannot read
the declared vocabulary through it — `commons.validator` doing so closed a cycle
(`entities` -> `graph` -> `commons` -> `entities`) that resolved only when some
unrelated module happened to be imported first. Layers below `entities` read the
vocabulary here instead of re-deriving it; three copies of a vocabulary is how
they drift.
"""

from __future__ import annotations

from science_model.profiles import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE

KIND_DESCRIPTORS = (*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds)

#: Relation name -> its declared kind. The same `RelationKind` records `materialize`
#: enforces endpoints against, indexed for callers that need to ask about a relation
#: without walking the profile.
RELATION_KINDS = {rk.name: rk for rk in CORE_PROFILE.relation_kinds}


def kind_can_author_relation(relation_name: str, kind: str) -> bool:
    """Whether ``kind`` is an admissible SOURCE endpoint for ``relation_name``.

    Mirrors the branching in `science_model.relations.relation_allows_kinds` -- which
    decides the same question for a *pair* -- so a caller asking "may this kind author
    this edge at all?" gets an answer that cannot disagree with the one materialize
    enforces. Deriving it is the point: a hand-listed copy is how the authored
    vocabulary and the relation model drifted apart in the first place.
    """
    relation = RELATION_KINDS.get(relation_name)
    if relation is None:
        return False
    if relation.allowed_kind_pairs:
        return any(pair.source_kind == kind for pair in relation.allowed_kind_pairs)
    return not relation.source_kinds or kind in relation.source_kinds

#: Kind -> the status vocabulary it declares. A kind declaring none is ABSENT
#: from this mapping rather than mapped to an empty set: the two mean different
#: things to `entities.valid_statuses`, which falls through to the project-local
#: manifest for an absent kind and would wrongly report a closed empty
#: vocabulary for a present-but-empty one.
DECLARED_STATUSES: dict[str, frozenset[str]] = {
    ek.name: frozenset(ek.statuses) for ek in KIND_DESCRIPTORS if ek.statuses
}

#: Kind -> whether it may be superseded (S2). Built over `KIND_DESCRIPTORS` -- the SHIPPED
#: profiles only -- exactly like `DECLARED_STATUSES`. That population is load-bearing: a kind
#: declared in a project manifest is ABSENT here and cannot enter the frozen `supported_kinds`
#: policy. Authored `sci:supersedes` admission independently resolves against the core relation
#: descriptor, so a project-local endpoint pair is refused. The writer itself supports
#: project-local status vocabularies; inertness does not depend on a write-time failure.
DECLARED_SUPERSEDABLE: dict[str, bool] = {ek.name: bool(ek.supersedable) for ek in KIND_DESCRIPTORS}
