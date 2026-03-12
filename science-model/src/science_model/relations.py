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
