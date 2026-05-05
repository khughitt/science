"""Helpers for working with declared relation kinds."""

from __future__ import annotations

from science_model.profiles.schema import RelationKind


def build_relation_registry(relations: list[RelationKind]) -> dict[str, RelationKind]:
    """Index relation kinds by name for fast lookup."""
    registry: dict[str, RelationKind] = {}
    for relation in relations:
        if relation.name in registry:
            msg = f"Duplicate relation kind: {relation.name}"
            raise ValueError(msg)
        registry[relation.name] = relation
    return registry


def relation_allows_kinds(relation: RelationKind, source_kind: str, target_kind: str) -> bool:
    """Return whether a relation kind permits a source-kind / target-kind pair.

    `allowed_kind_pairs`, when present, is the authoritative non-Cartesian
    allow-list. Otherwise, empty source/target kind lists retain their existing
    unrestricted meaning.
    """
    if relation.allowed_kind_pairs:
        return any(
            pair.source_kind == source_kind and pair.target_kind == target_kind
            for pair in relation.allowed_kind_pairs
        )
    source_allowed = not relation.source_kinds or source_kind in relation.source_kinds
    target_allowed = not relation.target_kinds or target_kind in relation.target_kinds
    return source_allowed and target_allowed
