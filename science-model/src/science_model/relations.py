"""Helpers for working with declared relation kinds."""

from __future__ import annotations

from science_model.profiles.schema import RelationKind


def build_relation_registry(relations: list[RelationKind]) -> dict[str, RelationKind]:
    """Index relation kinds by name for fast lookup."""
    return {relation.name: relation for relation in relations}
