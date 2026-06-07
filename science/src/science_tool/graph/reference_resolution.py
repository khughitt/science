"""Shared entity-reference resolution for audit and graph materialization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from science_model import normalize_alias
from science_model.entities import Entity

from science_tool.graph.sources import build_alias_map

if TYPE_CHECKING:
    from science_tool.graph.identity_table import IdentityTable


@dataclass(frozen=True)
class ReferenceResolution:
    """Resolution result for one authored entity reference."""

    status: str
    raw: str
    canonical_id: str | None = None
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReferenceResolver:
    """Resolve authored entity references with optional fallback rules."""

    alias_map: dict[str, str]
    slug_index: dict[str, frozenset[str]]
    owner_scopes: dict[str, frozenset[str]] = field(default_factory=dict)
    scope_names: frozenset[str] = frozenset()

    @classmethod
    def from_entities(
        cls,
        entities: list[Entity],
        *,
        manual_aliases: dict[str, str] | None = None,
        identity_table: "IdentityTable | None" = None,
    ) -> "ReferenceResolver":
        alias_map = build_alias_map(entities, manual_aliases=manual_aliases)
        identity_map = _build_identity_map(entities, alias_map)
        slug_index: dict[str, set[str]] = {}

        for entity in entities:
            canonical_id = entity.canonical_id
            if ":" not in canonical_id:
                continue
            _, slug = canonical_id.split(":", 1)
            slug_index.setdefault(slug.lower(), set()).add(identity_map.get(canonical_id, canonical_id))

        owner_scopes: dict[str, frozenset[str]] = {}
        scope_names: frozenset[str] = frozenset()
        if identity_table is not None:
            owner_scopes = identity_table.owner_scopes_by_id()
            scope_names = frozenset(scope for scopes in owner_scopes.values() for scope in scopes)

        return cls(
            alias_map=alias_map,
            slug_index={slug: frozenset(sorted(ids)) for slug, ids in slug_index.items()},
            owner_scopes=owner_scopes,
            scope_names=scope_names,
        )

    def resolve(
        self,
        raw: str,
        *,
        allow_cross_kind_fallback: bool = False,
        allow_tag: bool = False,
    ) -> ReferenceResolution:
        if raw.startswith("tag:"):
            return ReferenceResolution(status="tag" if allow_tag else "unresolved", raw=raw)

        # Scoped reference form <scope>:<kind>:<slug> (design §B3a): a leading
        # known-scope prefix names which scope's owner is meant. It resolves to the
        # same canonical id (scope is not part of the id) but only if that scope
        # actually owns the id.
        scope, inner = self._split_scope(raw)
        if scope is not None:
            inner_res = self._resolve_unscoped(inner, allow_cross_kind_fallback=allow_cross_kind_fallback)
            if (
                inner_res.status == "resolved"
                and inner_res.canonical_id is not None
                and scope in self.owner_scopes.get(inner_res.canonical_id, frozenset())
            ):
                return ReferenceResolution(status="resolved", raw=raw, canonical_id=inner_res.canonical_id)
            return ReferenceResolution(status="unresolved", raw=raw)

        resolution = self._resolve_unscoped(raw, allow_cross_kind_fallback=allow_cross_kind_fallback)
        if resolution.status == "resolved" and resolution.canonical_id is not None:
            scopes = self.owner_scopes.get(resolution.canonical_id, frozenset())
            if len(scopes) > 1:
                # bare id owned by an owner in >1 loaded scope -> refuse; a scoped
                # form is required (the search chain never shadows owner ambiguity).
                return ReferenceResolution(status="scope_ambiguous", raw=raw, candidates=tuple(sorted(scopes)))
        return resolution

    def _split_scope(self, raw: str) -> tuple[str | None, str]:
        """Split <scope>:<kind>:<slug> into (scope, <kind>:<slug>); (None, raw) if bare.

        A prefix counts as a scope only when it is a known loaded scope name AND the
        remainder is itself kind-qualified (contains a colon), so a bare `kind:slug`
        is never misread as scope `kind`.
        """
        if not self.scope_names or ":" not in raw:
            return (None, raw)
        head, rest = raw.split(":", 1)
        if head in self.scope_names and ":" in rest:
            return (head, rest)
        return (None, raw)

    def _resolve_unscoped(self, raw: str, *, allow_cross_kind_fallback: bool) -> ReferenceResolution:
        resolved = normalize_alias(raw, self.alias_map)
        if raw in self.alias_map or raw.lower() in self.alias_map:
            return ReferenceResolution(status="resolved", raw=raw, canonical_id=resolved)

        if not allow_cross_kind_fallback or ":" not in raw:
            return ReferenceResolution(status="unresolved", raw=raw)

        _, slug = raw.split(":", 1)
        identities = tuple(self.slug_index.get(slug.lower(), ()))
        if len(identities) == 1:
            return ReferenceResolution(status="resolved", raw=raw, canonical_id=identities[0])
        if len(identities) > 1:
            return ReferenceResolution(status="ambiguous", raw=raw, candidates=identities)
        return ReferenceResolution(status="unresolved", raw=raw)


def _build_identity_map(entities: list[Entity], alias_map: dict[str, str]) -> dict[str, str]:
    ids = {entity.canonical_id for entity in entities}
    parent = {canonical_id: canonical_id for canonical_id in ids}

    def find(canonical_id: str) -> str:
        trail: list[str] = []
        current = canonical_id
        while parent[current] != current:
            trail.append(current)
            current = parent[current]
        for item in trail:
            parent[item] = current
        return current

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        preferred, secondary = sorted((left_root, right_root))
        parent[secondary] = preferred

    for entity in entities:
        for raw_target in entity.same_as:
            resolved = normalize_alias(raw_target, alias_map)
            if resolved in ids:
                union(entity.canonical_id, resolved)

    return {canonical_id: find(canonical_id) for canonical_id in ids}
