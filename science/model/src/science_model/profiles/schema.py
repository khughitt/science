"""Profile schema for layered Science knowledge graph models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EntityKind(BaseModel):
    """An entity kind declared by a knowledge profile."""

    name: str
    canonical_prefix: str
    layer: str
    description: str
    entity_class: str | None = None  # "epistemic" | "operational" | "reference"; None defaults to caller's choice
    # Layout/status overrides for project-local markdown kinds (v3 layout). All
    # optional; defaults derive name->entities/<name>/, numeric strategy, "active".
    home: str | None = None
    strategy: str | None = None  # "numeric" | "citekey" (singleton is core-only)
    default_status: str | None = None
    statuses: list[str] | None = None
    # Structured-source declaration: a project-local kind whose entities are
    # generated/maintained as rows in a single-type YAML data file under
    # knowledge/sources/<profile>/ (NOT the multi-type entities.yaml/terms.yaml
    # aggregate). Each row loads as an owner of this kind. `structured_source` is
    # the filename relative to the profile sources dir; `structured_source_root_key`
    # is the YAML root key holding the row list (defaults to the kind `name`).
    structured_source: str | None = None
    structured_source_root_key: str | None = None


class RelationEndpointPair(BaseModel):
    """One allowed source-kind / target-kind pair for a relation kind."""

    source_kind: str
    target_kind: str


class RelationKind(BaseModel):
    """A relation kind declared by a knowledge profile."""

    name: str
    predicate: str
    source_kinds: list[str]
    target_kinds: list[str]
    allowed_kind_pairs: list[RelationEndpointPair] = Field(default_factory=list)
    layer: str
    description: str = ""


class ProfileManifest(BaseModel):
    """A composable profile describing supported entity and relation kinds."""

    name: str
    imports: list[str]
    entity_kinds: list[EntityKind]
    relation_kinds: list[RelationKind]
    strictness: Literal["core", "curated", "typed-extension"]
