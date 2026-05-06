"""Shared entity-reference resolution for audit and graph materialization."""

from __future__ import annotations

from dataclasses import dataclass

from science_model import normalize_alias
from science_model.entities import Entity

from science_tool.graph.sources import build_alias_map


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

    @classmethod
    def from_entities(
        cls,
        entities: list[Entity],
        *,
        manual_aliases: dict[str, str] | None = None,
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

        return cls(
            alias_map=alias_map,
            slug_index={slug: frozenset(sorted(ids)) for slug, ids in slug_index.items()},
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
