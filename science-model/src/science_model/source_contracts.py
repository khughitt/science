"""Typed canonical source contracts for structured KG authoring."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuthoredTargetedRelation(BaseModel):
    """An authored relation from a source record to another target."""

    predicate: str
    target: str
    graph_layer: str = "graph/knowledge"


class ModelSource(BaseModel):
    """Canonical model-layer source record."""

    canonical_id: str
    title: str
    profile: str
    source_path: str
    domain: str | None = None
    aliases: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    relations: list[AuthoredTargetedRelation] = Field(default_factory=list)


class ParameterSource(BaseModel):
    """Canonical parameter-layer source record."""

    canonical_id: str
    title: str
    symbol: str
    profile: str
    source_path: str
    units: str | None = None
    quantity_group: str | None = None
    domain: str | None = None
    aliases: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    relations: list[AuthoredTargetedRelation] = Field(default_factory=list)


class BindingSource(BaseModel):
    """Canonical model-parameter binding source record."""

    model: str
    parameter: str
    source_path: str
    symbol: str | None = None
    role: str | None = None
    units_override: str | None = None
    confidence: float | None = None
    match_tier: str | None = None
    default_value: float | None = None
    typical_range: list[float] | None = None
    source_refs: list[str] = Field(default_factory=list)
    notes: str | None = None
