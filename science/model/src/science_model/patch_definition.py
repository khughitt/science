"""Authored patch-definition source model.

Patch membership is derived compiled state. This module owns only the authored
intent: focal target, local scope, derivation policy, seeds, and excludes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from science_model.entities import EntityType, ProjectEntity


class PatchScope(BaseModel):
    """A future-shaped scope entry.

    v1 supports only the local project scope. The shape is explicit so later
    remote/commons scopes can extend it without replacing the field.
    """

    model_config = ConfigDict(extra="forbid")

    scope: Literal["local", "commons", "remote"] = "local"
    ref: str | None = None


class PatchExclude(BaseModel):
    """Authored curation constraint that suppresses a derived member."""

    model_config = ConfigDict(extra="forbid")

    ref: str
    reason: str

    @field_validator("ref", "reason")
    @classmethod
    def _non_empty(cls, value: str, info: ValidationInfo) -> str:
        if not value.strip():
            raise ValueError(f"{info.field_name} must be non-empty")
        return value


class LocalClosurePolicy(BaseModel):
    """The v1 local patch derivation policy."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["local-closure-v1"] = "local-closure-v1"
    version: Literal["local-closure-v1"] = "local-closure-v1"
    max_depth: int = Field(default=2, ge=1)


BoundaryRoleName = Literal["BoundaryIn", "BoundaryOut"]
FlowPredicate = Literal["feedsInto", "produces", "causes"]
InquiryProfileName = Literal["investigation", "causal"]
InquiryStatus = Literal["sketch", "specified", "planned", "in-progress", "complete"]


class BoundaryRole(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str
    role: BoundaryRoleName


class FlowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str
    predicate: FlowPredicate
    object: str
    claim_refs: list[str] = Field(default_factory=list)


class Param(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str
    source: str = ""
    ref: str = ""
    note: str = ""


class Assumption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str
    statement: str
    derived_from: str = ""


class Transformation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str
    tool: str = ""
    params: list[Param] = Field(default_factory=list)
    validated_by: str = ""


class InquiryProfile(BaseModel):
    """Authored investigation design layered on a patch."""

    model_config = ConfigDict(extra="forbid")

    profile: InquiryProfileName
    status: InquiryStatus = "sketch"
    boundary_roles: list[BoundaryRole] = Field(default_factory=list)
    flow_edges: list[FlowEdge] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    transformations: list[Transformation] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    treatment: str | None = None
    outcome: str | None = None

    @model_validator(mode="after")
    def _estimand_rules(self) -> "InquiryProfile":
        if self.profile == "causal" and (not (self.treatment or "").strip() or not (self.outcome or "").strip()):
            raise ValueError("causal profile requires both treatment and outcome")
        if self.profile == "investigation" and (self.treatment or self.outcome):
            raise ValueError("investigation profile must not set treatment/outcome (estimand is causal-only)")
        return self


class PatchDefinitionEntity(ProjectEntity):
    """Authored patch intent.

    The derived patch membership set is emitted during graph materialization;
    this entity never owns an authored member list.
    """

    kind: str = "patch-definition"
    type: Literal[EntityType.PATCH_DEFINITION] = EntityType.PATCH_DEFINITION  # type: ignore[assignment]

    focal: str
    scope_set: list[PatchScope] = Field(min_length=1)
    neighborhood_policy: LocalClosurePolicy
    seeds: list[str] = Field(default_factory=list)
    excludes: list[PatchExclude] = Field(default_factory=list)
    patch_type: Literal["neighborhood", "inquiry"] = "neighborhood"
    inquiry: InquiryProfile | None = None

    @field_validator("focal")
    @classmethod
    def _focal_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("focal must be non-empty")
        return value

    @field_validator("seeds")
    @classmethod
    def _seed_refs_non_empty(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value.strip():
                raise ValueError("seed refs must be non-empty")
        return values

    @model_validator(mode="after")
    def _v1_local_scope_only(self) -> "PatchDefinitionEntity":
        non_local = [entry for entry in self.scope_set if entry.scope != "local"]
        if non_local:
            raise ValueError("remote scopes deferred to a later spec")
        return self

    @model_validator(mode="after")
    def _inquiry_block_coherence(self) -> "PatchDefinitionEntity":
        if self.patch_type == "inquiry" and self.inquiry is None:
            raise ValueError("patch_type 'inquiry' requires an inquiry block")
        if self.patch_type != "inquiry" and self.inquiry is not None:
            raise ValueError("inquiry block is only allowed when patch_type is 'inquiry'")
        return self
