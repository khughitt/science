"""Profile schema for layered Science knowledge graph models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class EntityKind(BaseModel):
    """An entity kind declared by a knowledge profile."""

    name: str
    canonical_prefix: str
    layer: str
    description: str


class RelationKind(BaseModel):
    """A relation kind declared by a knowledge profile."""

    name: str
    predicate: str
    source_kinds: list[str]
    target_kinds: list[str]
    layer: str
    description: str = ""


class ProfileManifest(BaseModel):
    """A composable profile describing supported entity and relation kinds."""

    name: str
    imports: list[str]
    entity_kinds: list[EntityKind]
    relation_kinds: list[RelationKind]
    strictness: Literal["core", "curated", "typed-extension"]
