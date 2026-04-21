"""Shared types consumed by both graph/sources.py and the entity_providers package.

Lifted out of graph/sources.py so the entity_providers package can import these
types without creating an import cycle (entity_providers needs SourceEntity;
sources.py would otherwise need entity_providers for the resolver, closing the loop).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from science_model.reasoning import (
    ClaimLayer,
    EvidenceRole,
    IdentificationStrength,
    MeasurementModel,
    ProxyDirectness,
    RivalModelPacket,
    SupportScope,
)


class SourceEntity(BaseModel):
    """A canonical entity collected from project source files."""

    canonical_id: str
    kind: str
    title: str
    profile: str
    source_path: str
    provider: str
    domain: str | None = None
    confidence: float | None = None
    status: str | None = None
    content_preview: str = ""
    related: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    same_as: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    claim_layer: ClaimLayer | None = None
    identification_strength: IdentificationStrength | None = None
    proxy_directness: ProxyDirectness | None = None
    supports_scope: SupportScope | None = None
    independence_group: str | None = None
    evidence_role: EvidenceRole | None = None
    measurement_model: MeasurementModel | None = None
    rival_model_packet: RivalModelPacket | None = None


class SourceRelation(BaseModel):
    """An authored relation collected from structured source files."""

    subject: str
    predicate: str
    object: str
    graph_layer: str = "graph/knowledge"
    source_path: str


class KnowledgeProfiles(BaseModel):
    """Selected knowledge profiles for a project."""

    local: str = "local"


class EntityIdCollisionError(ValueError):
    """Raised when two providers (or a provider + a specialized parser) produce the same canonical_id."""

    def __init__(self, canonical_id: str, sources: list[tuple[str, str]]) -> None:
        self.canonical_id = canonical_id
        self.sources = sources  # list of (provider_name, source_path)
        msg = f"entity {canonical_id!r} produced by multiple sources:\n"
        for provider, path in sources:
            msg += f"  - {provider}: {path}\n"
        msg += "Resolve by removing one source, or migrate to a single backend."
        super().__init__(msg)


class EntityDatapackageInvalidError(ValueError):
    """Raised when a datapackage with science-pkg-entity-1.0 profile has invalid schema."""

    def __init__(self, datapackage_path: str, message: str) -> None:
        self.datapackage_path = datapackage_path
        super().__init__(f"{datapackage_path}: invalid entity-profile datapackage — {message}")
