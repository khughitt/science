"""Entity data models for Science research projects."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from science_model.packages.schema import AccessBlock, DerivationBlock
from science_model.reasoning import (
    ClaimLayer,
    IdentificationStrength,
    MeasurementModel,
    ProxyDirectness,
    SupportScope,
)
from science_model.sync import SyncSource


class EntityType(StrEnum):
    """Known entity types across Science projects."""

    CONCEPT = "concept"
    HYPOTHESIS = "hypothesis"
    QUESTION = "question"
    PROPOSITION = "proposition"
    OBSERVATION = "observation"
    INQUIRY = "inquiry"
    TOPIC = "topic"
    INTERPRETATION = "interpretation"
    DISCUSSION = "discussion"
    MODEL = "model"
    PLAN = "plan"
    ASSUMPTION = "assumption"
    TRANSFORMATION = "transformation"
    VARIABLE = "variable"
    DATASET = "dataset"
    METHOD = "method"
    EXPERIMENT = "experiment"
    ARTICLE = "article"
    WORKFLOW = "workflow"
    WORKFLOW_RUN = "workflow-run"
    WORKFLOW_STEP = "workflow-step"
    DATA_PACKAGE = "data-package"
    RESEARCH_PACKAGE = "research-package"
    FINDING = "finding"
    STORY = "story"
    PAPER = "paper"
    SEARCH = "search"
    REPORT = "report"
    VALIDATION_REPORT = "validation-report"
    UNKNOWN = "unknown"


class EntityUpdate(BaseModel):
    """Partial update for entity metadata (written back to frontmatter)."""

    status: str | None = None
    related: list[str] | None = None


class Entity(BaseModel):
    """A research entity parsed from frontmatter or the knowledge graph."""

    id: str
    canonical_id: str = ""
    type: EntityType
    title: str
    status: str | None = None
    project: str
    profile: str = "core"
    domain: str | None = None
    ontology_terms: list[str]
    created: date | None = None
    updated: date | None = None
    related: list[str]
    same_as: list[str] = Field(default_factory=list)
    source_refs: list[str]
    content_preview: str
    content: str = ""
    file_path: str
    # Type-specific
    maturity: str | None = None
    confidence: float | None = None
    datasets: list[str] | None = None
    aliases: list[str] = Field(default_factory=list)
    pre_registered: bool = False
    pre_registered_date: date | None = None
    sync_source: SyncSource | None = None
    claim_layer: ClaimLayer | None = None
    identification_strength: IdentificationStrength | None = None
    proxy_directness: ProxyDirectness | None = None
    supports_scope: SupportScope | None = None
    independence_group: str | None = None
    measurement_model: MeasurementModel | None = None
    rival_model_packet_ref: str | None = None
    # Dataset entity unification (rev 2.2)
    origin: str | None = None  # "external" | "derived"
    access: AccessBlock | None = None
    derivation: DerivationBlock | None = None
    accessions: list[str] = Field(default_factory=list)
    datapackage: str = ""
    local_path: str = ""
    consumed_by: list[str] = Field(default_factory=list)
    parent_dataset: str = ""
    siblings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _fill_derived_defaults(self) -> "Entity":
        if not self.canonical_id:
            self.canonical_id = self.id
        return self

    @model_validator(mode="after")
    def _enforce_origin_block_invariants(self) -> "Entity":
        """Invariants #7/#8: origin ⟺ which top-level block applies (datasets only)."""
        if self.type != EntityType.DATASET or self.origin is None:
            return self
        if self.origin == "external":
            if self.access is None:
                raise ValueError(f"{self.id}: origin=external requires an access block (invariant #7)")
            if self.derivation is not None:
                raise ValueError(f"{self.id}: origin=external must not carry a derivation block (invariant #7)")
        elif self.origin == "derived":
            if self.derivation is None:
                raise ValueError(f"{self.id}: origin=derived requires a derivation block (invariant #8)")
            if self.access is not None:
                raise ValueError(f"{self.id}: origin=derived must not carry an access block (invariant #8)")
            if self.accessions:
                raise ValueError(f"{self.id}: origin=derived must not carry accessions (invariant #8)")
            if self.local_path:
                raise ValueError(f"{self.id}: origin=derived must not carry local_path (invariant #8)")
        else:
            raise ValueError(f"{self.id}: origin must be 'external' or 'derived', got {self.origin!r}")
        return self


class ProjectEntity(Entity):
    """Entity about the conduct of a science project (tasks, hypotheses, datasets...).

    Sub-base for the operational / epistemic side of the model family per
    the unified-entity-model spec §Entity Subfamilies.

    Typed entities (TaskEntity, DatasetEntity, WorkflowRunEntity,
    ResearchPackageEntity) extend ProjectEntity in science_model.entities.

    Design contract (not yet Pydantic-enforced): project-specific fields
    like `blocked_by`, `maturity`, reasoning metadata belong here rather
    than on base Entity. Field location is a documented design intent;
    the move off Entity is a post-plan cleanup.
    """

    pass


class DomainEntity(Entity):
    """Entity about external domain subject matter (diseases, pathways, chemicals...).

    Sub-base for domain-grounded entities per the unified-entity-model spec
    §Entity Subfamilies. Initial Science core ships this empty — domain-specific
    fields arrive through project extensions registered via EntityRegistry.

    Design contract: domain-grounded synonym/authority metadata belongs here
    rather than on base Entity.
    """

    pass
