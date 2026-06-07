from __future__ import annotations

from science_model.entities import Entity, EntityType

from science_tool.graph.identity_table import (
    IdentityDeclaration,
    IdentityTable,
    ParticipationMode,
)
from science_tool.graph.reference_resolution import ReferenceResolver


def _entity(
    cid: str,
    kind: str,
    etype: EntityType,
    *,
    related: list[str] | None = None,
    same_as: list[str] | None = None,
) -> Entity:
    k, _slug = cid.split(":", 1)
    return Entity(
        id=cid,
        canonical_id=cid,
        kind=kind,
        type=etype,
        title=cid,
        project="proj",
        ontology_terms=[],
        related=related or [],
        same_as=same_as or [],
        source_refs=[],
        content_preview="",
        file_path=f"entities/{k}/{_slug}.md",
    )


def _owner(cid: str, scope: str) -> IdentityDeclaration:
    return IdentityDeclaration(
        canonical_id=cid,
        participation_mode=ParticipationMode.OWNER,
        owner_scope=scope,
        adapter="markdown",
        source_ref=None,
    )


def _resolver_two_scope() -> ReferenceResolver:
    # one entity (dedup keeps one) but the identity table records two owner scopes
    entities = [_entity("topic:bayesian", "topic", EntityType.TOPIC)]
    table = IdentityTable(rows=[_owner("topic:bayesian", "proj"), _owner("topic:bayesian", "commons")])
    return ReferenceResolver.from_entities(entities, identity_table=table)


def test_bare_ref_owned_in_two_scopes_is_scope_ambiguous() -> None:
    res = _resolver_two_scope().resolve("topic:bayesian")
    assert res.status == "scope_ambiguous"
    assert res.candidates == ("commons", "proj")  # sorted owning scopes


def test_scoped_ref_resolves_to_named_owner_scope() -> None:
    res = _resolver_two_scope().resolve("commons:topic:bayesian")
    assert res.status == "resolved"
    assert res.canonical_id == "topic:bayesian"  # scope is not part of the id


def test_unknown_scope_prefix_is_treated_as_bare_and_unresolved() -> None:
    # "other" is NOT a loaded scope name -> _split_scope leaves it bare -> a bare
    # lookup of the whole "other:topic:bayesian" string fails -> unresolved.
    res = _resolver_two_scope().resolve("other:topic:bayesian")
    assert res.status == "unresolved"


def test_scoped_ref_to_loaded_scope_that_does_not_own_is_unresolved() -> None:
    # "other" IS a loaded scope (it owns a different id), so the prefix is parsed as
    # a scope; but "other" does not own topic:bayesian, so the scoped form is
    # rejected (not silently resolved) -> unresolved.
    entities = [_entity("topic:bayesian", "topic", EntityType.TOPIC)]
    table = IdentityTable(
        rows=[
            _owner("topic:bayesian", "proj"),
            _owner("topic:bayesian", "commons"),
            _owner("decision:d1", "other"),  # makes "other" a known loaded scope name
        ]
    )
    resolver = ReferenceResolver.from_entities(entities, identity_table=table)
    assert "other" in resolver.scope_names  # precondition: prefix is parseable as a scope
    res = resolver.resolve("other:topic:bayesian")
    assert res.status == "unresolved"


def test_bare_ref_owned_in_one_scope_is_resolved_not_ambiguous() -> None:
    entities = [_entity("hypothesis:h1", "hypothesis", EntityType.HYPOTHESIS)]
    table = IdentityTable(rows=[_owner("hypothesis:h1", "proj")])
    res = ReferenceResolver.from_entities(entities, identity_table=table).resolve("hypothesis:h1")
    assert res.status == "resolved"
    assert res.canonical_id == "hypothesis:h1"


def test_kind_qualified_bare_ref_not_misparsed_as_scope() -> None:
    # A bare `kind:slug` must never be read as scope=`kind`, even if a scope shares
    # that name. Here scope "topic" exists, and "topic:bayesian" is a bare id whose
    # remainder ("bayesian") has no colon -> treated as bare, resolves normally.
    entities = [_entity("topic:bayesian", "topic", EntityType.TOPIC)]
    table = IdentityTable(rows=[_owner("topic:bayesian", "topic")])  # scope literally named "topic"
    res = ReferenceResolver.from_entities(entities, identity_table=table).resolve("topic:bayesian")
    assert res.status == "resolved"
    assert res.canonical_id == "topic:bayesian"


def test_same_as_secondary_two_scopes_cross_kind_is_scope_ambiguous() -> None:
    # Regression: a same_as-merged SECONDARY id owned in two scopes must surface
    # scope_ambiguous even via the slug-index cross-kind path. topic:zzz has
    # same_as topic:aaa -> they merge with union-find root topic:aaa (alpha-first).
    # The cross-kind lookup of "other:zzz" returns the root topic:aaa, but the
    # owner_scopes table records the two scopes under the SECONDARY id topic:zzz,
    # so the len(scopes) > 1 guard must still fire on the root's cluster.
    entities = [
        _entity("topic:aaa", "topic", EntityType.TOPIC),
        _entity("topic:zzz", "topic", EntityType.TOPIC, same_as=["topic:aaa"]),
    ]
    table = IdentityTable(rows=[_owner("topic:zzz", "proj"), _owner("topic:zzz", "commons")])
    resolver = ReferenceResolver.from_entities(entities, identity_table=table)

    # Alias path on the secondary's own id already fires (returns topic:zzz, a 1:1
    # owner_scopes key) — guard this stays correct.
    alias_res = resolver.resolve("topic:zzz")
    assert alias_res.status == "scope_ambiguous"

    # Cross-kind / slug-index path: returns the union-find root topic:aaa. Before
    # the fix this resolved silently, bypassing scope ambiguity.
    cross_res = resolver.resolve("other:zzz", allow_cross_kind_fallback=True)
    assert cross_res.status == "scope_ambiguous"
    assert cross_res.candidates == ("commons", "proj")


def test_backward_compatible_without_identity_table() -> None:
    # No identity_table -> no scope parsing, no ambiguity: identical to legacy behavior.
    entities = [_entity("topic:bayesian", "topic", EntityType.TOPIC)]
    resolver = ReferenceResolver.from_entities(entities)  # legacy call
    assert resolver.resolve("topic:bayesian").status == "resolved"
    assert resolver.resolve("commons:topic:bayesian").status == "unresolved"
    assert resolver.scope_names == frozenset()
    assert resolver.owner_scopes == {}
