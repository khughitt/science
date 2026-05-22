"""Entity data models for Science research projects."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, field_validator, model_validator

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
from science_model.source_contracts import AuthoredTargetedRelation
from science_model.sync import SyncSource


class ChainAuditInterpretation(StrEnum):
    EVIDENCE_FOR = "evidence-for"
    EVIDENCE_AGAINST = "evidence-against"
    MIXED = "mixed"
    INCONCLUSIVE = "inconclusive"


class BayesFactorEvidence(BaseModel):
    """Bayes-factor-style evidence carried by a chain-audit.

    `interpretation` is the load-bearing field; `bf10` is optional because
    many chain audits are categorical (no numeric BF available).
    """

    hypothesis_ref: str
    null_baseline: str
    interpretation: ChainAuditInterpretation
    bf10: float | None = None

    @model_validator(mode="after")
    def _validate_bf10_positive(self) -> "BayesFactorEvidence":
        if self.bf10 is not None and self.bf10 <= 0:
            raise ValueError("bf10 must be a positive number when set")
        return self

    @model_validator(mode="after")
    def _validate_null_baseline_nonempty(self) -> "BayesFactorEvidence":
        if not self.null_baseline.strip():
            raise ValueError("null_baseline must be non-empty")
        return self


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
    THEME = "theme"
    MECHANISM = "mechanism"
    PAPER = "paper"
    SEARCH = "search"
    REPORT = "report"
    VALIDATION_REPORT = "validation-report"
    TASK = "task"
    SPEC = "spec"
    CANONICAL_PARAMETER = "canonical_parameter"
    CODE_FILE = "code-file"
    UNKNOWN = "unknown"


class EntityClass(StrEnum):
    """High-level taxonomic classification of an entity kind.

    Distinguishes which kinds carry continuous belief (epistemic), which
    represent operational artifacts produced by project work (operational),
    and which name external things that rarely change (reference).

    Used by the freshness engine to decide whether an entity participates
    in `bears_on` propagation: only EPISTEMIC entities are valid targets.
    """

    EPISTEMIC = "epistemic"
    OPERATIONAL = "operational"
    REFERENCE = "reference"


class EpistemicReviewState(BaseModel):
    """Per-entity review-as-of state for epistemic entities.

    `last_reviewed` is the date the user (or agent) last considered this
    entity in light of all evidence. `last_review_note` is an optional
    human-readable note about that review. `review_horizon_days` is an
    optional per-entity threshold for the `stale` state — when set,
    entities whose `last_reviewed` is older than `now - horizon` flip
    to `stale` even without any upstream change.
    """

    last_reviewed: date | None = None
    last_review_note: str = ""
    review_horizon_days: int | None = None

    @model_validator(mode="after")
    def _validate_horizon(self) -> "EpistemicReviewState":
        if self.review_horizon_days is not None and self.review_horizon_days <= 0:
            raise ValueError("review_horizon_days must be positive when set")
        return self


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
        EntityType.CODE_FILE.value,
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
    relations: list[AuthoredTargetedRelation] = Field(default_factory=list)
    commits_to: list[str] | None = None
    same_as: list[str] = Field(default_factory=list)
    source_refs: list[str]
    evidence_refs: list[str] = Field(default_factory=list)
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
    review_state: EpistemicReviewState | None = None

    @model_validator(mode="after")
    def _validate_review_state_kind(self) -> "Entity":
        # Closed list of clearly-non-epistemic core kinds. Avoids registry
        # coupling at the science-model layer while still rejecting the
        # high-confidence cases.
        non_epistemic = {
            "task",
            "dataset",
            "workflow-run",
            "data-package",
            "paper",
            "experiment",
            "code-file",
        }
        if self.review_state is not None and self.kind in non_epistemic:
            raise ValueError(f"review_state is not allowed on kind {self.kind!r} (non-epistemic by design)")
        return self

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
    produced_by: list[str] = Field(default_factory=list)
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

    @model_validator(mode="after")
    def _validate_produced_by(self) -> "Entity":
        if not self.produced_by:
            return self
        if self.kind not in ("dataset", "data-package"):
            raise ValueError(f"produced_by is only allowed on dataset/data-package entities, not {self.kind!r}")
        for ref in self.produced_by:
            if not ref.startswith("code-file:"):
                raise ValueError(f"produced_by entries must be code-file:<id> references, got {ref!r}")
        return self


class Readiness(BaseModel):
    """Result of evaluating an entity's readiness for downstream use.

    `state` is a short, display-ready label (e.g. "done", "embargoed",
    "controlled, unverified"). `detail` is an optional one-line elaboration
    rendered by `tasks show`.
    """

    ready: bool
    state: str
    detail: str = ""


class ReadinessResolverProtocol(Protocol):
    """Structural protocol implemented by science's ReadinessResolver."""

    def resolve_ref(self, ref: str) -> Readiness: ...


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

    def readiness(self, resolver: ReadinessResolverProtocol | None = None) -> Readiness:
        """Default readiness: ready iff status == 'done'.

        `resolver` is optional context for subclasses that need to traverse
        other entities (e.g. derived datasets → producing workflow-run).
        Subclasses without cross-entity dependencies ignore it.
        """
        if self.status == "done":
            return Readiness(ready=True, state="done")
        return Readiness(ready=False, state=self.status or "unknown")


class DomainEntity(Entity):
    """Entity about external domain subject matter (diseases, pathways, chemicals...).

    Sub-base for domain-grounded entities per the unified-entity-model spec
    §Entity Subfamilies. Initial Science core ships this empty — domain-specific
    fields arrive through project extensions registered via EntityRegistry.

    Design contract: domain-grounded synonym/authority metadata belongs here
    rather than on base Entity.
    """

    pass


class StructuralChainEntity(Entity):
    """A first-class structural decomposition: an ordered chain of >=2 entity refs.

    Chain links are restricted at the relation-kind layer to mechanism, model,
    proposition, observation, or finding. Link-kind enforcement happens at
    materialize-time via `relation_allows_kinds(has_link, ...)` -- this model
    only enforces shape (length, no duplicates).
    """

    chain: list[str]

    @model_validator(mode="after")
    def _validate_chain_shape(self) -> "StructuralChainEntity":
        if len(self.chain) < 2:
            raise ValueError("structural-chain requires at least two links")
        if len(set(self.chain)) != len(self.chain):
            raise ValueError("structural-chain links must be distinct (no duplicates)")
        return self


_INTERPRETATION_TO_COMPOSITE: dict[ChainAuditInterpretation, str] = {
    ChainAuditInterpretation.EVIDENCE_FOR: "[+]",
    ChainAuditInterpretation.EVIDENCE_AGAINST: "[-]",
    ChainAuditInterpretation.MIXED: "[~]",
    ChainAuditInterpretation.INCONCLUSIVE: "[?]",
}


class ChainAuditEntity(Entity):
    """A verdict over a structural-chain.

    Carries both a `verdict:` block (compatible with verdict/parser.py) and a
    `bayes_factor_evidence:` block. The validator enforces consistency
    between `verdict.composite` and `bayes_factor_evidence.interpretation`
    via the documented mapping table.
    """

    audits: str
    proposition_refs: list[str] = Field(default_factory=list)
    bayes_factor_evidence: BayesFactorEvidence
    verdict: dict
    rationale: str = ""

    @model_validator(mode="after")
    def _validate_verdict_consistency(self) -> "ChainAuditEntity":
        composite = self.verdict.get("composite")
        if composite is None:
            raise ValueError("verdict.composite is required on chain-audit")
        expected = _INTERPRETATION_TO_COMPOSITE[self.bayes_factor_evidence.interpretation]
        if composite != expected:
            raise ValueError(
                f"verdict.composite ({composite!r}) inconsistent with "
                f"bayes_factor_evidence.interpretation "
                f"({self.bayes_factor_evidence.interpretation.value!r}); "
                f"expected composite {expected!r}"
            )
        return self


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


class ThemeEntity(ProjectEntity):
    """Durable cross-cutting organizing frame for project knowledge."""

    theme_kind: Literal[
        "methodological",
        "biological",
        "translational",
        "evidence-quality",
        "organizational",
        "conceptual",
        "empirical",
        "domain",
    ] = "methodological"
    theme_scope: Literal[
        "project",
        "federation",
        "child",
        "cross-project",
    ] = "project"
    summary: str = ""


class PaperEntity(ProjectEntity):
    """Paper — typed entity carrying commons paper mixin fields."""

    bibkey: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1800, le=2200)
    venue: str = ""
    doi: str = ""
    pmid: str = ""
    url: str = ""
    datasets: list[str] = Field(default_factory=list)
    key_findings: list[str] = Field(default_factory=list)
    methods_summary: str = ""
    limitations: list[str] = Field(default_factory=list)

    @field_validator("authors", mode="before")
    @classmethod
    def _coerce_scalar_authors(cls, value: object) -> object:
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("bibkey", "venue", "doi", "pmid", "url", "methods_summary", mode="before")
    @classmethod
    def _coerce_nullable_strings(cls, value: object) -> object:
        if value is None:
            return ""
        return value


class TaskEntity(ProjectEntity):
    """Task — typed entity for research tasks.

    Inherits all Entity/ProjectEntity fields. Task-specific invariants (if any)
    live here as @model_validator methods. In the initial implementation, no
    task-specific invariants are enforced beyond what ProjectEntity provides.

    Note: science_model.tasks.Task remains a parse-layer helper for the task DSL.
    The TaskAdapter (Task 9) converts parsed Task records into TaskEntity raw
    records for registry-based validation.
    """

    task_type: str = ""
    priority: str = "P2"
    aspects: list[str] = Field(default_factory=list)
    parent: str = ""
    group: str = ""
    artifacts: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    completed: date | None = None


class DatasetEntity(ProjectEntity):
    """Dataset — typed entity with rev 2.2 invariants (origin/access/derivation).

    Invariant #7 (origin=external → access required) and #8 (origin=derived →
    derivation and/or code produced_by required) are enforced on this typed subclass.
    """

    tier: str = ""
    update_cadence: str = ""

    @model_validator(mode="after")
    def _enforce_dataset_invariants(self) -> "DatasetEntity":
        """Invariants #7/#8: origin ⟺ which provenance applies.

        (produced_by is constrained to code-file refs and to dataset/data-package
        kinds by the base Entity validator added in Task 2; here we only enforce
        the origin-specific rules.)

        external: access required; no derivation, no produced_by (raw input
        cannot claim code produced it).
        derived: at least one provenance path — a derivation block and/or
        non-empty code-only produced_by; no access/accessions/local_path.
        """
        if self.origin is None:
            return self
        if self.origin == "external":
            if self.access is None:
                raise ValueError(f"{self.id}: origin=external requires an access block (invariant #7)")
            if self.derivation is not None:
                raise ValueError(f"{self.id}: origin=external must not carry a derivation block (invariant #7)")
            if self.produced_by:
                raise ValueError(f"{self.id}: origin=external must not carry produced_by (invariant #7)")
        elif self.origin == "derived":
            if self.derivation is None and not self.produced_by:
                raise ValueError(f"{self.id}: origin=derived requires a derivation or produced_by block (invariant #8)")
            if self.access is not None:
                raise ValueError(f"{self.id}: origin=derived must not carry an access block (invariant #8)")
            if self.accessions:
                raise ValueError(f"{self.id}: origin=derived must not carry accessions (invariant #8)")
            if self.local_path:
                raise ValueError(f"{self.id}: origin=derived must not carry local_path (invariant #8)")
        else:
            raise ValueError(f"{self.id}: origin must be 'external' or 'derived', got {self.origin!r}")
        return self

    def readiness(self, resolver: ReadinessResolverProtocol | None = None) -> Readiness:
        if self.origin == "external":
            return self._external_readiness()
        if self.origin == "derived":
            return self._derived_readiness(resolver)
        return Readiness(ready=False, state="unknown", detail=f"unknown origin {self.origin!r}")

    def _external_readiness(self) -> Readiness:
        access = self.access
        if access is None:
            # Should be unreachable per invariant #7, but guard anyway.
            return Readiness(ready=False, state="missing-access-block")
        if access.availability == "withdrawn":
            return Readiness(ready=False, state="withdrawn")
        if access.availability == "embargoed":
            detail = f"available_after: {access.available_after}" if access.available_after else ""
            return Readiness(ready=False, state="embargoed", detail=detail)
        # availability == "available"
        if access.exception.mode:
            mode = access.exception.mode
            rationale = access.exception.rationale
            if mode == "expanded-to-acquire":
                return Readiness(ready=False, state="acquiring", detail=rationale)
            if mode in ("scope-reduced", "substituted"):
                return Readiness(ready=True, state=f"consumable-via-{mode}", detail=rationale)
            # Unknown mode — defensive fallthrough for model_construct() bypass; pydantic
            # Literal validation prevents this path under normal construction.
            return Readiness(ready=False, state=f"exception:{mode}", detail=rationale)
        if access.verified:
            return Readiness(ready=True, state="available")
        return Readiness(ready=False, state=f"{access.level}, unverified")

    def _derived_readiness(self, resolver: ReadinessResolverProtocol | None) -> Readiness:
        if resolver is None:
            return Readiness(
                ready=False,
                state="unknown",
                detail="derived dataset readiness requires resolver context",
            )
        if self.derivation is None:
            return Readiness(ready=False, state="missing-derivation-block")
        return resolver.resolve_ref(self.derivation.workflow_run)


class WorkflowRunEntity(ProjectEntity):
    """Workflow run — readiness is `complete` when status == 'complete'."""

    manifest_path: str = ""
    resources: list[dict[str, Any]] = Field(default_factory=list)

    def readiness(self, resolver: ReadinessResolverProtocol | None = None) -> Readiness:
        if self.status == "complete":
            return Readiness(ready=True, state="complete")
        return Readiness(ready=False, state=self.status or "unknown")


class ResearchPackageEntity(ProjectEntity):
    """Research package — placeholder typed entity for package composition."""

    pass


class CodeFileEntity(ProjectEntity):
    """A source-code file registered as a first-class entity.

    Operational: carries no continuous belief. `updated` is set by the
    CodeAdapter to the file's last content-changing commit date so code
    edits feed freshness once provenance edges exist (Plan C). `task_ids`
    are stored here rather than in `related` so an unresolved task id
    cannot hard-fail graph materialization (validated in Plan B).
    """

    decision_bearing: bool = False
    task_ids: list[str] = Field(default_factory=list)
