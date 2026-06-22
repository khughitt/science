"""Profile schema for layered Science knowledge graph models."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from science_model.identity import EntityClass

EntityFilenameStrategy = Literal["numeric", "citekey", "singleton", "slug", "verbatim", "id-local"]


class KindCategory(StrEnum):
    """Named-contract taxonomy for kinds (design §2.3)."""

    AUTHORED_CORE = "authored-core"
    RESERVED = "reserved"
    SOURCE_ONLY = "source-only"


class EntityKind(BaseModel):
    """An entity kind declared by a knowledge profile."""

    name: str
    canonical_prefix: str
    layer: str
    description: str
    entity_class: EntityClass | None = None
    category: KindCategory | None = None  # None for project-local kinds (only built-in profiles set it)
    template_ready: bool = False  # renders through the migrated Renderer path (== today's MIGRATED_KINDS)
    shortform: str | None = None  # single-letter CLI alias, e.g. "h" -> hypothesis
    # Layout/status overrides for project-local markdown kinds (v3 layout). All
    # optional; defaults derive name->entities/<name>/, numeric strategy, "active".
    home: str | None = None
    strategy: str | None = None  # raw manifest input; the EntityFilenameStrategy vocab is enforced tool-side by the path-policy loader, not at the schema boundary
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


class CoreStructuredSource(BaseModel):
    """Attach a structured-source data file to an existing CORE entity kind.

    Unlike `EntityKind.structured_source` (which declares a project-LOCAL kind),
    this augments a core kind the project does not own: its rows are generated
    into a single-type YAML file under knowledge/sources/<profile>/ and load as
    owners of that core kind, WITHOUT registering/shadowing the core kind. Use
    for generated bulk core entities (e.g. `finding` rows emitted by an audit)
    that would otherwise have to ride the multi-type aggregate v3 retirement
    forbids. `structured_source` is the filename relative to the profile sources
    dir; `structured_source_root_key` is the YAML root key holding the row list
    (defaults to `kind`).
    """

    kind: str
    structured_source: str
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
    core_structured_sources: list[CoreStructuredSource] = Field(default_factory=list)
