from __future__ import annotations

from typing import NotRequired, TypedDict

from rdflib import URIRef


class InquiryEdge(TypedDict):
    subject: str
    predicate: str
    object: str
    claims: NotRequired[list[str]]


class InquiryInfo(TypedDict):
    slug: str
    label: str
    status: str
    inquiry_type: str
    target: str
    created: str
    description: str
    treatment: str | None
    outcome: str | None
    related: list[str]
    boundary_in: list[str]
    boundary_out: list[str]
    edges: list[InquiryEdge]


class ClaimSummaryData(TypedDict):
    uri: URIRef
    claim: str
    label: str
    text: str
    belief_state: str
    contested: bool
    belief_display: str
    support_count: int
    dispute_count: int
    source_count: int
    evidence_types: list[str]
    has_empirical_data: bool
    statistical_support: str
    mechanistic_support: str
    replication_scope: str
    claim_status: str
    pre_registration_count: int
    pre_registrations: list[str]
    interaction_count: int
    interaction_modifiers: list[str]
    bridge_count: int
    bridge_hypotheses: list[str]
    signals: list[str]
    risk_score: float


class NeighborhoodSummaryData(TypedDict):
    center_uri: URIRef
    label: str
    text: str
    neighbor_claim_count: int
    avg_risk_score: float
    contested_count: int
    single_source_count: int
    no_empirical_count: int
    structural_fragility: str
    neighborhood_risk: float


class QuestionSummaryData(TypedDict):
    uri: URIRef
    question: str
    label: str
    text: str
    claim_count: int
    neighborhood_count: int
    avg_risk_score: float
    contested_claim_count: int
    single_source_claim_count: int
    no_empirical_claim_count: int
    priority_score: float


class PropositionEvidenceLine(TypedDict):
    source: str
    kind: str
    datasets: list[str]


class PropositionPhase1Metadata(TypedDict, total=False):
    compositional_status: str
    compositional_method: str
    compositional_note: str
    platform_pattern: str
    dataset_effects: dict[str, float]
    evidence_lines: list[PropositionEvidenceLine]
    claim_layer: str
    supports_scope: str
    measurement_model: dict[str, object]
    rival_model_packet: dict[str, object]


class PropositionEvidenceSemantics(TypedDict, total=False):
    statistical_support: str
    mechanistic_support: str
    replication_scope: str
    claim_status: str
    identification_strength: str
    proxy_directness: str
    independence_group: str
    evidence_role: str


class PropositionInteractionTerm(TypedDict):
    modifier: str
    effect: str
    note: NotRequired[str]


class FalsificationRecord(TypedDict, total=False):
    uri: str
    predicted: str
    observed: str
    decision: str
    source_of_prediction: str
    supersedes_claim: str


class EvidenceClaimBundle(TypedDict, total=False):
    uri: str
    text: str
    confidence: float | None
    sources: list[str]
    support_count: int
    dispute_count: int
    claim_layer: str
    identification_strength: str
    proxy_directness: str
    supports_scope: str
    independence_group: str
    evidence_role: str
    measurement_model: dict[str, object]
    rival_model_packet: dict[str, object]
    compositional_status: str
    compositional_method: str
    compositional_note: str
    platform_pattern: str
    dataset_effects: dict[str, float]
    evidence_lines: list[PropositionEvidenceLine]
    statistical_support: str
    mechanistic_support: str
    replication_scope: str
    claim_status: str
    pre_registrations: list[str]
    interaction_terms: list[PropositionInteractionTerm]
    bridge_between: list[str]
    falsifications: list[FalsificationRecord]


class EvidenceEdgeOverlay(TypedDict):
    claims: list[EvidenceClaimBundle]


class EvidenceOverlayData(TypedDict):
    edges: dict[str, EvidenceEdgeOverlay]


class InquirySummaryData(TypedDict):
    uri: URIRef
    inquiry: str
    label: str
    text: str
    inquiry_type: str
    status: str
    claim_count: int
    backed_claim_count: int
    avg_risk_score: float
    contested_claim_count: int
    single_source_claim_count: int
    no_empirical_claim_count: int
    priority_score: float


class ProjectSummaryData(TypedDict):
    project: str
    profile: str
    question_count: int
    inquiry_count: int
    claim_count: int
    high_risk_neighborhood_count: int
    avg_risk_score: float
    contested_claim_count: int
    single_source_claim_count: int
    no_empirical_claim_count: int
    priority_score: float


class EvidenceSignalSummary(TypedDict):
    support_count: int
    dispute_count: int
    support_sources: set[str]
    dispute_sources: set[str]
    source_count: int
