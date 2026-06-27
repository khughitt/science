"""Entity data models for Science research projects."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, field_validator, model_validator

from science_model.identity import (  # noqa: F401  (EntityClass re-exported; relocated to identity in Spec 2)
    EntityClass,
    EntityScope,
    ExternalId,
)
from science_model.packages.schema import (
    AccessBlock,
    BenchmarkBlock,
    DatasetUsage,
    DerivationBlock,
    MemberOfDerivationBlock,
    WorkflowRecipeDerivationBlock,
)
from science_model.reasoning import (
    RESERVED_COMPOSITION_RULES,
    ClaimLayer,
    CompositionRule,
    DisputeScope,
    EvidenceRole,
    EvidenceStance,
    EvidenceStrength,
    EvidenceType,
    IdentificationStrength,
    IndependenceTag,
    MeasurementModel,
    ProxyDirectness,
    RivalModelPacket,
    SupportScope,
    canonical_evidence_type_token,
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
    CONSTRUCT = "construct"
    HYPOTHESIS = "hypothesis"
    QUESTION = "question"
    RESEARCH_QUESTION = "research-question"
    PROPOSITION = "proposition"
    PATCH_DEFINITION = "patch-definition"
    OBSERVATION = "observation"
    OUTCOME = "outcome"
    INQUIRY = "inquiry"
    TOPIC = "topic"
    INTERPRETATION = "interpretation"
    DISCUSSION = "discussion"
    MODEL = "model"
    PLAN = "plan"
    PRE_REGISTRATION = "pre-registration"
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
    STRUCTURAL_CHAIN = "structural-chain"
    CHAIN_AUDIT = "chain-audit"
    DATA_PACKAGE = "data-package"
    RESEARCH_PACKAGE = "research-package"
    CURATION_SWEEP = "curation-sweep"
    FINDING = "finding"
    STORY = "story"
    THEME = "theme"
    MECHANISM = "mechanism"
    PAPER = "paper"
    PROSE_SOURCE = "prose-source"
    BOOK = "book"
    TALK = "talk"
    SEARCH = "search"
    REPORT = "report"
    SYNTHESIS = "synthesis"
    VALIDATION_REPORT = "validation-report"
    TASK = "task"
    SPEC = "spec"
    DECISION = "decision"
    CLAIM_REGISTRY = "claim-registry"
    CANONICAL_PARAMETER = "canonical_parameter"
    CODE_FILE = "code-file"
    EVIDENCE_LINE = "evidence-line"
    UNKNOWN = "unknown"


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
        EntityType.SYNTHESIS.value,
        EntityType.VALIDATION_REPORT.value,
        EntityType.TASK.value,
        EntityType.SPEC.value,
        EntityType.CANONICAL_PARAMETER.value,
        EntityType.CODE_FILE.value,
        EntityType.PATCH_DEFINITION.value,
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
    composition_rule: CompositionRule | None = None

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
            "prose-source",
            "book",
            "experiment",
            "code-file",
        }
        if self.review_state is not None and self.kind in non_epistemic:
            raise ValueError(f"review_state is not allowed on kind {self.kind!r} (non-epistemic by design)")
        return self

    @model_validator(mode="after")
    def _validate_dataset_taxonomy(self) -> "Entity":
        # Pillar A (A-D1/A-D4): on dataset entities, source_class is a small epistemic
        # class and derived_kind is required exactly when source_class == "derived".
        # Lives on Entity (gated to kind) — not DatasetEntity — so it also covers the
        # parse_entity_file path, which returns a plain Entity for datasets.
        if self.kind != "dataset":
            if self.benchmark is not None:
                raise ValueError(f"{self.id}: benchmark metadata is only valid on dataset entities")
            return self
        if self.source_class is not None and self.source_class not in (
            "observational",
            "derived",
            "reference",
        ):
            raise ValueError(
                f"{self.id}: source_class must be observational|derived|reference, "
                f"got {self.source_class!r}"
            )
        if self.source_class == "derived":
            if self.derived_kind not in ("aggregate", "transform", "model_output"):
                raise ValueError(
                    f"{self.id}: source_class=derived requires derived_kind "
                    f"(aggregate|transform|model_output), got {self.derived_kind!r}"
                )
        elif self.derived_kind is not None:
            raise ValueError(
                f"{self.id}: derived_kind is only allowed when source_class=derived "
                f"(got source_class={self.source_class!r})"
            )
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
    derivation: DerivationBlock | WorkflowRecipeDerivationBlock | MemberOfDerivationBlock | None = None
    accessions: list[str] = Field(default_factory=list)
    datapackage: str = ""
    local_path: str = ""
    consumed_by: list[str] = Field(default_factory=list)
    produced_by: list[str] = Field(default_factory=list)
    parent_dataset: str = ""
    siblings: list[str] = Field(default_factory=list)
    # Dataset license (SPDX id or sentinel). On Entity (gated to kind) so the
    # parse_entity_file path, which returns a plain Entity for datasets, keeps it.
    license: str = ""
    # Pillar A — epistemic class (orthogonal to origin) + co-owned forward provenance
    source_class: str | None = None       # "observational" | "derived" | "reference"
    dataset_class: Literal["deposit", "reference", "pointer"] = "deposit"
    derived_kind: str | None = None        # "aggregate" | "transform" | "model_output"
    dataset_usage: list[DatasetUsage] = Field(default_factory=list)
    benchmark: BenchmarkBlock | None = None

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

    @model_validator(mode="after")
    def _validate_composition_rule(self) -> "Entity":
        if self.composition_rule is None:
            return self
        if self.kind not in ("hypothesis", "mechanism"):
            raise ValueError(
                f"composition_rule is only meaningful on bundle kinds (hypothesis/mechanism), "
                f"not {self.kind!r}; remove it."
            )
        if self.composition_rule in RESERVED_COMPOSITION_RULES:
            raise ValueError(
                f"composition_rule {self.composition_rule.value!r} is reserved and not "
                "implemented in v1 (see docs/plans/2026-06-11-bundle-belief-rollup-design.md "
                "§4); use 'all_steps' or 'conjunctive'."
            )
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


class BookEntity(ProjectEntity):
    """Book — typed entity for a long-form monograph summarized chapter-by-chapter.

    A source that *provides* evidence (like `paper`) but carries no truth-apt
    claim of its own, so it is OPERATIONAL / non-epistemic — never a
    `bears_on`/belief target.
    """

    bibkey: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1800, le=2200)
    publisher: str = ""
    isbn: str = ""
    doi: str = ""
    url: str = ""
    key_findings: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("authors", mode="before")
    @classmethod
    def _coerce_scalar_authors(cls, value: object) -> object:
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("bibkey", "publisher", "isbn", "doi", "url", mode="before")
    @classmethod
    def _coerce_nullable_strings(cls, value: object) -> object:
        if value is None:
            return ""
        return value


class TalkEntity(ProjectEntity):
    """Talk — recorded seminar / conference presentation.

    A source that *provides* evidence (like `paper`) but is not peer-reviewed and
    carries no truth-apt claim of its own, so it is OPERATIONAL — never a
    `bears_on`/belief target. Keeping it distinct from `paper` lets downstream
    evidence-weighting treat an unrefereed talk differently from a published paper.
    """

    bibkey: str = ""
    speakers: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1800, le=2200)
    date_presented: date | None = None
    venue: str = ""
    url: str = ""
    transcript_path: str = ""
    doi: str = ""
    duration_minutes: int | None = Field(default=None, ge=0)
    key_points: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)

    @field_validator("speakers", mode="before")
    @classmethod
    def _coerce_scalar_speakers(cls, value: object) -> object:
        if isinstance(value, str):
            return [value]
        return value

    @field_validator("bibkey", "venue", "url", "transcript_path", "doi", mode="before")
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
    qa_report: str = ""  # project-root-relative path to a qa_report.json from `science datasets qa`

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
        if self.derivation is None:
            if self.produced_by:
                return Readiness(ready=True, state="derived-via-code")
            return Readiness(ready=False, state="missing-provenance")
        if isinstance(self.derivation, MemberOfDerivationBlock):
            # member_of derivations do not have a workflow-run reference;
            # treat as structurally-derived (the row lookup is the consuming
            # instance's responsibility, not a pipeline run).
            return Readiness(ready=True, state="derived-via-member-of")
        if isinstance(self.derivation, WorkflowRecipeDerivationBlock):
            return Readiness(ready=True, state="derived-via-workflow-recipe")
        if resolver is None:
            return Readiness(
                ready=False,
                state="unknown",
                detail="derived dataset readiness requires resolver context",
            )
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

    decision_bearing: bool | None = None
    executable: bool = False
    task_ids: list[str] = Field(default_factory=list)


class QuantitativeResult(BaseModel):
    """Typed posterior / fitted-model summary carried by an evidence-line.

    All fields are optional so that partial results (e.g. only ``fit_task``
    known at staging time) are accepted without validation errors.

    ``hdi`` is a two-element [low, high] credible-interval list.
    ``fit_task`` and ``model`` record the provenance of the estimate.
    """

    beta: float | None = None
    hdi: list[float] | None = None
    prob_sign: float | None = None
    fit_task: str | None = None
    model: str | None = None


class EvidenceLineEntity(ProjectEntity):
    """A first-class evidence-line entity linking a source to a target claim.

    ``stance`` and ``target`` are required. All other evidence-metadata fields
    are optional.

    Independence metadata (``independence``, ``shared_*``) records whether
    multiple evidence lines draw on the same underlying data source; this is
    used by the freshness/belief engine to avoid double-counting.

    Note: ``independence_group`` and ``measurement_model`` are inherited from
    Entity; ``evidence_role`` is inherited from ProjectEntity.

    ``quantitative_result`` carries a typed posterior summary (beta/hdi/
    prob_sign/fit_task/model) when the line has an associated fitted model.

    ``belief_eligible`` is a staging marker (default True). When False the
    line may exist but emits no cito:supports/disputes and cannot enter belief
    aggregation until grounding completes. Enforcement is twofold: the validate
    check ``evidence.empirical.requires_dataset_usage`` flags belief-eligible
    empirical lines lacking ``dataset_usage``, and materialization skips
    ``belief_eligible=False`` lines from cito emission and the belief graph.
    """

    stance: EvidenceStance
    target: str
    source: str | None = None
    strength: EvidenceStrength | None = None
    independence: IndependenceTag | None = None
    dispute_scope: DisputeScope | None = None
    shared_dataset: str | None = None
    shared_lab: str | None = None
    shared_platform: str | None = None
    shared_cohort: str | None = None
    evidence_type: EvidenceType | None = None
    quantitative_result: QuantitativeResult | None = None
    belief_eligible: bool = True

    @field_validator("evidence_type", mode="before")
    @classmethod
    def _canonicalize_evidence_type(cls, value: object) -> object:
        # Strip the authored ``_evidence`` suffix so both spellings parse to the same
        # EvidenceType member; an unknown token falls through to enum coercion, which raises.
        if isinstance(value, str):
            return canonical_evidence_type_token(value)
        return value


class InquiryEntity(ProjectEntity):
    """A scoped research inquiry (boundary + estimand over the knowledge graph).

    `target` is the entity the inquiry is about; doc-authored inquiries carry it
    in frontmatter and it materializes as sci:target, mirroring the
    `science inquiry` CLI mutation path.
    """

    target: str | None = None
