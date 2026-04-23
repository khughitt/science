"""Entity data models for Science research projects."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from science_model.identity import EntityScope, ExternalId
from science_model.packages.schema import AccessBlock, DerivationBlock
from science_model.reasoning import (
    ClaimLayer,
    EvidenceRole,
    IdentificationStrength,
    MeasurementModel,
    ProxyDirectness,
    RivalModelPacket,
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
    MECHANISM = "mechanism"
    PAPER = "paper"
    SEARCH = "search"
    REPORT = "report"
    VALIDATION_REPORT = "validation-report"
    TASK = "task"
    SPEC = "spec"
    CANONICAL_PARAMETER = "canonical_parameter"
    UNKNOWN = "unknown"


class EntityUpdate(BaseModel):
    """Partial update for entity metadata (written back to frontmatter)."""

    status: str | None = None
    related: list[str] | None = None


_CORE_KIND_TO_TYPE: dict[str, EntityType] = {entity_type.value: entity_type for entity_type in EntityType}


def core_entity_type_for_kind(kind: str) -> EntityType | None:
    """Return the core EntityType projection for a kind, if one exists."""
    return _CORE_KIND_TO_TYPE.get(kind)


_DISALLOWED_MECHANISM_PARTICIPANT_KINDS = frozenset(
    {
        EntityType.HYPOTHESIS.value,
        EntityType.QUESTION.value,
        EntityType.PROPOSITION.value,
        EntityType.OBSERVATION.value,
        EntityType.INQUIRY.value,
        EntityType.TOPIC.value,
        EntityType.INTERPRETATION.value,
        EntityType.DISCUSSION.value,
        EntityType.MODEL.value,
        EntityType.PLAN.value,
        EntityType.ASSUMPTION.value,
        EntityType.TRANSFORMATION.value,
        EntityType.VARIABLE.value,
        EntityType.DATASET.value,
        EntityType.METHOD.value,
        EntityType.EXPERIMENT.value,
        EntityType.ARTICLE.value,
        EntityType.WORKFLOW.value,
        EntityType.WORKFLOW_RUN.value,
        EntityType.WORKFLOW_STEP.value,
        EntityType.DATA_PACKAGE.value,
        EntityType.RESEARCH_PACKAGE.value,
        EntityType.FINDING.value,
        EntityType.STORY.value,
        EntityType.MECHANISM.value,
        EntityType.PAPER.value,
        EntityType.SEARCH.value,
        EntityType.REPORT.value,
        EntityType.VALIDATION_REPORT.value,
        EntityType.TASK.value,
        EntityType.SPEC.value,
        EntityType.CANONICAL_PARAMETER.value,
        EntityType.UNKNOWN.value,
    }
)


def _is_valid_mechanism_participant(ref: str) -> bool:
    if ":" not in ref:
        return False
    kind = ref.split(":", 1)[0].strip()
    if not kind:
        return False
    if kind == EntityType.CONCEPT.value:
        return True
    if kind in _DISALLOWED_MECHANISM_PARTICIPANT_KINDS:
        return False
    return core_entity_type_for_kind(kind) is None


class Entity(BaseModel):
    """A research entity parsed from frontmatter or the knowledge graph."""

    id: str
    canonical_id: str = ""
    kind: str
    type: EntityType | None = None
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
    primary_external_id: ExternalId | None = None
    xrefs: list[ExternalId] = Field(default_factory=list)
    scope: EntityScope = EntityScope.PROJECT
    provisional: bool = False
    review_after: date | None = None
    deprecated_ids: list[str] = Field(default_factory=list)
    replaced_by: str | None = None
    taxon: str | None = None
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
    def _validate_kind_type_consistency(self) -> "Entity":
        expected = core_entity_type_for_kind(self.kind)
        if self.type != expected:
            raise ValueError("kind/type mismatch")
        return self

    @model_validator(mode="after")
    def _validate_identity_fields(self) -> "Entity":
        if self.canonical_id in self.deprecated_ids:
            raise ValueError("deprecated_ids must not include the entity canonical_id")
        if self.replaced_by is not None and self.replaced_by == self.canonical_id:
            raise ValueError("replaced_by must not equal the entity canonical_id")
        if len({xref.curie for xref in self.xrefs}) != len(self.xrefs):
            raise ValueError("xrefs must not contain duplicate external ids")
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

    # Project-scoped operational fields. `blocked_by` tracks cross-entity
    # blocking relationships (task blocked by another task, hypothesis blocked
    # by missing dataset, etc.); previously lived on SourceEntity.
    blocked_by: list[str] = Field(default_factory=list)
    # Reasoning-metadata fields carried on propositions and project-scoped
    # entities. `rival_model_packet` is the full packet model (as opposed
    # to `rival_model_packet_ref: str | None` on Entity which records a
    # reference only). `evidence_role` was previously on SourceEntity.
    evidence_role: EvidenceRole | None = None
    rival_model_packet: RivalModelPacket | None = None


class DomainEntity(Entity):
    """Entity about external domain subject matter (diseases, pathways, chemicals...).

    Sub-base for domain-grounded entities per the unified-entity-model spec
    §Entity Subfamilies. Initial Science core ships this empty — domain-specific
    fields arrive through project extensions registered via EntityRegistry.

    Design contract: domain-grounded synonym/authority metadata belongs here
    rather than on base Entity.
    """

    pass


class MechanismEntity(ProjectEntity):
    """Structured explanatory bundle with explicit participants and propositions."""

    participants: list[str] = Field(default_factory=list)
    propositions: list[str] = Field(default_factory=list)
    summary: str = ""

    @model_validator(mode="after")
    def _validate_mechanism_shape(self) -> "MechanismEntity":
        if len(self.participants) < 2:
            raise ValueError("mechanism requires at least two participants")
        if any(not _is_valid_mechanism_participant(ref) for ref in self.participants):
            raise ValueError("mechanism participants must be domain/catalog entities or concept entities")
        if not self.propositions:
            raise ValueError("mechanism requires at least one proposition")
        if not self.summary.strip():
            raise ValueError("mechanism requires a non-empty summary")
        return self


class TaskEntity(ProjectEntity):
    """Task — typed entity for research tasks.

    Inherits all Entity/ProjectEntity fields. Task-specific invariants (if any)
    live here as @model_validator methods. In the initial implementation, no
    task-specific invariants are enforced beyond what ProjectEntity provides.

    Note: science_model.tasks.Task remains a parse-layer helper for the task DSL.
    The TaskAdapter (Task 9) converts parsed Task records into TaskEntity raw
    records for registry-based validation.
    """

    pass


class DatasetEntity(ProjectEntity):
    """Dataset — typed entity with rev 2.2 invariants (origin/access/derivation).

    Invariant #7 (origin=external → access required) and #8 (origin=derived →
    derivation required) are enforced on this typed subclass.
    """

    @model_validator(mode="after")
    def _enforce_dataset_invariants(self) -> "DatasetEntity":
        """Invariants #7/#8: origin ⟺ which top-level block applies."""
        if self.origin is None:
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


class WorkflowRunEntity(ProjectEntity):
    """Workflow run — placeholder typed entity.

    Workflow-run-specific semantics (production metadata, provenance refs) can
    be added as @model_validator methods here as they're formalized.
    """

    pass


class ResearchPackageEntity(ProjectEntity):
    """Research package — placeholder typed entity for package composition."""

    pass
