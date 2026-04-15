"""Reusable reasoning metadata models for Science projects."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ClaimLayer(StrEnum):
    """Authored layer for a proposition or claim."""

    EMPIRICAL_REGULARITY = "empirical_regularity"
    CAUSAL_EFFECT = "causal_effect"
    MECHANISTIC_NARRATIVE = "mechanistic_narrative"
    STRUCTURAL_CLAIM = "structural_claim"


class IdentificationStrength(StrEnum):
    """How much causal leverage an evidence line carries."""

    NONE = "none"
    STRUCTURAL = "structural"
    OBSERVATIONAL = "observational"
    LONGITUDINAL = "longitudinal"
    INTERVENTIONAL = "interventional"


class ProxyDirectness(StrEnum):
    """How directly a line refers to the construct of interest."""

    DIRECT = "direct"
    INDIRECT = "indirect"
    DERIVED = "derived"


class SupportScope(StrEnum):
    """How widely authored support should be reviewed."""

    LOCAL_PROPOSITION = "local_proposition"
    HYPOTHESIS_BUNDLE = "hypothesis_bundle"
    CROSS_HYPOTHESIS = "cross_hypothesis"
    PROJECT_WIDE = "project_wide"


class EvidenceRole(StrEnum):
    """Role a line plays in support or criticism."""

    DIRECT_TEST = "direct_test"
    PROXY_SUPPORT = "proxy_support"
    BACKGROUND_CONSTRAINT = "background_constraint"
    NEGATIVE_CONTROL = "negative_control"
    MODEL_CRITICISM = "model_criticism"


class MeasurementModel(BaseModel):
    """A proxy-mediated mapping between an observed entity and a latent construct."""

    observed_entity: str = Field(min_length=1)
    latent_construct: str | None = None
    measurement_relation: str | None = None
    rationale: str | None = None
    known_failure_modes: list[str] = Field(default_factory=list)
    substitutable_with: list[str] = Field(default_factory=list)


class RivalModelPacket(BaseModel):
    """A bounded set of rival models for explicit comparison."""

    packet_id: str = Field(min_length=1)
    target_hypothesis: str | None = None
    target_inquiry: str | None = None
    current_working_model: str | None = None
    alternative_models: list[str] = Field(default_factory=list)
    shared_observables: list[str] = Field(default_factory=list)
    discriminating_predictions: list[str] = Field(default_factory=list)
    adjudication_rule: str | None = None


class EvidenceLineMetadata(BaseModel):
    """Authored reasoning metadata for an evidence line or proposition."""

    claim_layer: ClaimLayer | None = None
    identification_strength: IdentificationStrength | None = None
    proxy_directness: ProxyDirectness | None = None
    supports_scope: SupportScope | None = None
    independence_group: str | None = None
    evidence_role: EvidenceRole | None = None
    measurement_model: MeasurementModel | None = None
    rival_model_packet_ref: str | None = None
