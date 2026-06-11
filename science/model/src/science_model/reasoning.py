"""Reusable reasoning metadata models for Science projects."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Predicate(StrEnum):
    """v1 seed-set of sign-free binary predicates for relational propositions."""

    AFFECTS = "affects"
    REGULATES = "regulates"
    ASSOCIATES_WITH = "associates_with"
    BINDS = "binds"
    IS_PROXY_FOR = "is_proxy_for"
    INDUCES_STATE = "induces_state"
    TRANSITIONS_TO = "transitions_to"
    SUBTYPE_OF = "subtype_of"
    PART_OF = "part_of"


class Polarity(StrEnum):
    """Sign of a relational proposition (meaningful only for sign-apt predicates)."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNSIGNED = "unsigned"
    NOT_APPLICABLE = "not_applicable"


SIGN_MEANINGFUL_PREDICATES: frozenset[Predicate] = frozenset(
    {Predicate.AFFECTS, Predicate.REGULATES, Predicate.ASSOCIATES_WITH}
)


class ClaimLayer(StrEnum):
    """Authored layer for a proposition or claim."""

    EMPIRICAL_REGULARITY = "empirical_regularity"
    CAUSAL_EFFECT = "causal_effect"
    MECHANISTIC_NARRATIVE = "mechanistic_narrative"
    STRUCTURAL_CLAIM = "structural_claim"


class IdentificationStrength(StrEnum):
    """How much causal leverage an evidence line carries.

    The first five values lie on a rough continuum from weakest to strongest
    in-system identification. ``ANALOGICAL`` is off the continuum: it covers
    evidence that is interventional or longitudinal in a model system but
    only extrapolates to the target system by analogy (e.g. Drosophila
    perturbation read as an analogue for mammalian mechanism). Use
    ``proxy_directness`` and ``measurement_model.known_failure_modes`` to
    record the analogy gap.
    """

    NONE = "none"
    STRUCTURAL = "structural"
    OBSERVATIONAL = "observational"
    LONGITUDINAL = "longitudinal"
    INTERVENTIONAL = "interventional"
    ANALOGICAL = "analogical"


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


class EvidenceStance(StrEnum):
    """Whether an evidence line supports or disputes a claim."""

    SUPPORTS = "supports"
    DISPUTES = "disputes"


class EvidenceStrength(StrEnum):
    """Qualitative strength of an evidence line (matches ``graph add evidence --strength``)."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class IndependenceTag(StrEnum):
    """Evidence-line independence category (matches ``graph add evidence --independence``)."""

    INDEPENDENT = "independent"
    SHARED_SOURCE = "shared-source"
    CIRCULAR = "circular"


class DisputeScope(StrEnum):
    """Scope of a disputing evidence line — which aspect of the claim it targets."""

    WHOLE_CLAIM = "whole_claim"
    GENERALIZATION = "generalization"
    MECHANISM = "mechanism"
    BOUNDARY = "boundary"


class CompositionRule(StrEnum):
    """How a bundle (hypothesis/mechanism) composes its member propositions.

    `all_steps`/`conjunctive` share the v1 weakest-link implementation but keep
    distinct names to preserve authored intent. `evidence_union`/`faceted_support`
    are RESERVED — declared so the names are stable, but not implemented in v1
    (see docs/plans/2026-06-11-bundle-belief-rollup-design.md §4).
    """

    ALL_STEPS = "all_steps"            # mechanism default — every step must hold
    CONJUNCTIVE = "conjunctive"        # hypothesis default — sub-claims jointly assert the conjecture
    EVIDENCE_UNION = "evidence_union"  # RESERVED
    FACETED_SUPPORT = "faceted_support"  # RESERVED


RESERVED_COMPOSITION_RULES = frozenset({CompositionRule.EVIDENCE_UNION, CompositionRule.FACETED_SUPPORT})
WEAKEST_LINK_COMPOSITION_RULES = frozenset({CompositionRule.ALL_STEPS, CompositionRule.CONJUNCTIVE})


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


class PropositionMetadata(BaseModel):
    """Authored reasoning metadata for a proposition."""

    claim_layer: ClaimLayer | None = None
    identification_strength: IdentificationStrength | None = None
    proxy_directness: ProxyDirectness | None = None
    supports_scope: SupportScope | None = None
    independence_group: str | None = None
    evidence_role: EvidenceRole | None = None
    measurement_model: MeasurementModel | None = None
    rival_model_packet_ref: str | None = None
