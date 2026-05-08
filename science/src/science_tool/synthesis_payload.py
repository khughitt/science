"""Synthesis-family payload registry and validation."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from science_tool.evidence_payload import (
    EvidencePayload,
    EvidencePayloadRegistry,
    ExtensionSpec,
    PayloadValidationError,
    ValidationRole,
)


SYNTHESIS_OPERATION_EXTENSION = "synthesis-operation"
SynthesisPermission = ValidationRole


class SynthesisOperation(BaseModel):
    """Common operation section required by every synthesis-family payload."""

    model_config = ConfigDict(extra="forbid")

    output_artifact_refs: list[str] = Field(default_factory=list)
    operator_assumption_refs: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class SynthesisFamilySpec:
    """Cross-cutting metadata for a t023 synthesis family."""

    family: str
    default_permission: SynthesisPermission
    max_permission: SynthesisPermission
    primary_owner: str | None
    typical_outputs: tuple[str, ...]
    reserved: bool = False


_PERMISSION_RANK: dict[SynthesisPermission, int] = {
    "record-only": 0,
    "quality-record-only": 1,
    "prioritize-attention": 2,
    "create-hypothesis": 3,
    "gate-update": 4,
    "strengthen-belief": 5,
}


SYNTHESIS_FAMILIES: dict[str, SynthesisFamilySpec] = {
    "effect-size-pooling": SynthesisFamilySpec(
        family="effect-size-pooling",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t022",
        typical_outputs=("pooled effect payload", "heterogeneity diagnostics"),
    ),
    "hypothesis-support-synthesis": SynthesisFamilySpec(
        family="hypothesis-support-synthesis",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t022",
        typical_outputs=("support payload", "posterior/probability summary"),
    ),
    "bayesian-model-comparison": SynthesisFamilySpec(
        family="bayesian-model-comparison",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t022",
        typical_outputs=("posterior model probabilities", "Bayes factors", "inclusion probabilities"),
    ),
    "diagnostic-test-synthesis": SynthesisFamilySpec(
        family="diagnostic-test-synthesis",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t022",
        typical_outputs=("sensitivity/specificity payload", "latent-class diagnostic summary"),
    ),
    "truth-discovery": SynthesisFamilySpec(
        family="truth-discovery",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t024",
        typical_outputs=("truth labels", "source reliability scores", "conflict diagnostics"),
    ),
    "decision-analytic-score": SynthesisFamilySpec(
        family="decision-analytic-score",
        default_permission="record-only",
        max_permission="prioritize-attention",
        primary_owner=None,
        typical_outputs=("MCDA score sets", "curation rankings", "triage lists"),
        reserved=True,
    ),
    "data-cleaning-repair": SynthesisFamilySpec(
        family="data-cleaning-repair",
        default_permission="quality-record-only",
        max_permission="prioritize-attention",
        primary_owner="task:t024",
        typical_outputs=("cleaned values", "repair uncertainty", "transformation record"),
    ),
    "causal-meta-analysis": SynthesisFamilySpec(
        family="causal-meta-analysis",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t026",
        typical_outputs=("causal effect estimate", "transport/estimand diagnostics"),
    ),
    "causal-discovery-synthesis": SynthesisFamilySpec(
        family="causal-discovery-synthesis",
        default_permission="prioritize-attention",
        max_permission="create-hypothesis",
        primary_owner="task:t034",
        typical_outputs=("graph object", "graph posterior", "candidate causal propositions"),
    ),
    "llm-prior-constraint-synthesis": SynthesisFamilySpec(
        family="llm-prior-constraint-synthesis",
        default_permission="record-only",
        max_permission="prioritize-attention",
        primary_owner="task:t034",
        typical_outputs=("weak priors", "constraints", "variable proposals"),
    ),
    "mechanistic-network-synthesis": SynthesisFamilySpec(
        family="mechanistic-network-synthesis",
        default_permission="prioritize-attention",
        max_permission="create-hypothesis",
        primary_owner="task:t034",
        typical_outputs=("candidate mechanism graph", "module/pathway hypothesis"),
    ),
    "mediation-synthesis": SynthesisFamilySpec(
        family="mediation-synthesis",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t034",
        typical_outputs=("direct effect payloads", "indirect effect payloads"),
    ),
    "mendelian-randomization-graph-synthesis": SynthesisFamilySpec(
        family="mendelian-randomization-graph-synthesis",
        default_permission="prioritize-attention",
        max_permission="strengthen-belief",
        primary_owner="task:t034",
        typical_outputs=("MR graph posterior", "MR effect estimate"),
    ),
    "graph-diagnostic-synthesis": SynthesisFamilySpec(
        family="graph-diagnostic-synthesis",
        default_permission="quality-record-only",
        max_permission="quality-record-only",
        primary_owner="task:t034",
        typical_outputs=("compatibility checks", "graph validation report"),
    ),
    "graph-estimate-synthesis": SynthesisFamilySpec(
        family="graph-estimate-synthesis",
        default_permission="prioritize-attention",
        max_permission="create-hypothesis",
        primary_owner="task:t035",
        typical_outputs=("conditional-dependence graph", "common/unique component graph"),
    ),
    "graph-posterior-synthesis": SynthesisFamilySpec(
        family="graph-posterior-synthesis",
        default_permission="prioritize-attention",
        max_permission="create-hypothesis",
        primary_owner="task:t035",
        typical_outputs=("graph samples", "edge inclusion table", "posterior summary"),
    ),
    "integrative-clustering-synthesis": SynthesisFamilySpec(
        family="integrative-clustering-synthesis",
        default_permission="prioritize-attention",
        max_permission="create-hypothesis",
        primary_owner="task:t035",
        typical_outputs=("cluster assignments", "subtype hypotheses"),
    ),
    "feature-selection-synthesis": SynthesisFamilySpec(
        family="feature-selection-synthesis",
        default_permission="prioritize-attention",
        max_permission="prioritize-attention",
        primary_owner="task:t035",
        typical_outputs=("selected-feature set", "relevance posterior", "stability report"),
    ),
    "module-discovery-synthesis": SynthesisFamilySpec(
        family="module-discovery-synthesis",
        default_permission="prioritize-attention",
        max_permission="create-hypothesis",
        primary_owner="task:t035",
        typical_outputs=("module/pathway membership artifact",),
    ),
    "predictive-integration-synthesis": SynthesisFamilySpec(
        family="predictive-integration-synthesis",
        default_permission="quality-record-only",
        max_permission="prioritize-attention",
        primary_owner="task:t035",
        typical_outputs=("predictive model", "risk score", "validation artifact"),
    ),
}


SYNTHESIS_PRIMARY_EXTENSION_NAMES: tuple[str, ...] = tuple(
    family for family, spec in SYNTHESIS_FAMILIES.items() if not spec.reserved
)


def build_synthesis_registry() -> EvidencePayloadRegistry:
    """Build a registry containing t023 synthesis families and the shared operation extension."""

    registry = EvidencePayloadRegistry()
    registry.register_extension(
        ExtensionSpec(
            name=SYNTHESIS_OPERATION_EXTENSION,
            artifact_type=SYNTHESIS_OPERATION_EXTENSION,
            required_fields=["output_artifact_refs", "operator_assumption_refs"],
            owning_task="task:t023",
        )
    )
    for family, spec in SYNTHESIS_FAMILIES.items():
        if spec.reserved:
            continue
        registry.register_extension(
            ExtensionSpec(
                name=family,
                artifact_type=family,
                co_required_extensions=[SYNTHESIS_OPERATION_EXTENSION],
                owning_task=spec.primary_owner,
            )
        )
    return registry


def validate_synthesis_payload(payload: EvidencePayload, registry: EvidencePayloadRegistry | None = None) -> None:
    """Validate t023 synthesis-family constraints on top of the generic payload contract."""

    family = payload.core.artifact_type
    try:
        spec = SYNTHESIS_FAMILIES[family]
    except KeyError as exc:
        raise PayloadValidationError(f"unknown synthesis family {family!r}") from exc
    if spec.reserved:
        raise PayloadValidationError(f"reserved synthesis family {family!r} cannot be used in production payloads")
    if not payload.core.extensions or payload.core.extensions[0] != family:
        raise PayloadValidationError(
            f"synthesis payload primary extension must be {family!r}; got {payload.core.extensions!r}"
        )
    if _PERMISSION_RANK[payload.core.validation_role] > _PERMISSION_RANK[spec.max_permission]:
        raise PayloadValidationError(
            f"validation_role {payload.core.validation_role!r} exceeds max permission {spec.max_permission!r} "
            f"for synthesis family {family!r}"
        )

    active_registry = registry or build_synthesis_registry()
    active_registry.validate_payload(payload)
    SynthesisOperation.model_validate(payload.extension_sections[SYNTHESIS_OPERATION_EXTENSION])
