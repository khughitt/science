"""Fixed ordinal rankings for evidence quality (design §2 rule 2, Phase 1).

Ordering is fixed here; per-project numeric weights and the quantitative scalar are
Phase 2 (opt-in via core/decisions.md). Unknown values rank 0 (degrade gracefully).
The evidence vocabularies are owned by ``science_model.reasoning`` (EvidenceType /
EvidenceRole / EvidenceStrength); the rank tables below key off those enum members and
are kept in lock-step by ``_reconcile_evidence_vocab``. Authored evidence_type values may
carry an '_evidence' suffix; ``normalize_evidence_type`` delegates suffix-stripping to the
model's ``canonical_evidence_type_token``.
"""
from __future__ import annotations

from science_model.reasoning import (
    EvidenceRole,
    EvidenceStrength,
    EvidenceType,
    canonical_evidence_type_token,
)

STANCE_SUPPORTS = "supports"
STANCE_DISPUTES = "disputes"

ROLE_DIRECT_TEST = EvidenceRole.DIRECT_TEST
ROLE_PROXY_SUPPORT = EvidenceRole.PROXY_SUPPORT
ROLE_BACKGROUND = EvidenceRole.BACKGROUND_CONSTRAINT
ROLE_NEGATIVE_CONTROL = EvidenceRole.NEGATIVE_CONTROL
ROLE_MODEL_CRITICISM = EvidenceRole.MODEL_CRITICISM

INDEPENDENT = "independent"
SHARED_SOURCE = "shared-source"
CIRCULAR = "circular"

SCOPE_WHOLE_CLAIM = "whole_claim"
GATED_PROXY = frozenset({"indirect", "derived"})
DIAGNOSTIC_ROLES = frozenset({ROLE_NEGATIVE_CONTROL, ROLE_MODEL_CRITICISM})

# Keyed on EvidenceType members. StrEnum keys resolve by string value too, so
# lookups like EVIDENCE_TYPE_RANK.get("empirical_data") still work unchanged.
EVIDENCE_TYPE_RANK = {
    EvidenceType.EMPIRICAL_DATA: 4,
    EvidenceType.BENCHMARK: 3,
    EvidenceType.SIMULATION: 3,
    EvidenceType.LITERATURE: 2,
    EvidenceType.EXPERT_JUDGMENT: 1,
}
# Valid-but-unranked-by-design types (rank 0), parallel to diagnostic roles.
UNRANKED_EVIDENCE_TYPES = frozenset({EvidenceType.NEGATIVE_RESULT})
EVIDENCE_ROLE_RANK = {
    EvidenceRole.DIRECT_TEST: 3,
    EvidenceRole.PROXY_SUPPORT: 2,
    EvidenceRole.BACKGROUND_CONSTRAINT: 1,
}
STRENGTH_RANK = {EvidenceStrength.STRONG: 3, EvidenceStrength.MODERATE: 2, EvidenceStrength.WEAK: 1}
# Canonical belief-magnitude names, lowest→highest. belief_weights imports nothing
# internal, so this is the cycle-free home for the magnitude strings that belief_policy
# validates against (BeliefMagnitude itself lives in belief.py, which would form a cycle).
# A reconciliation test (tests/test_belief_weights.py) keeps this in lock-step with the enum.
MAGNITUDE_NAMES = ("speculative", "fragile", "supported", "well_supported")


def normalize_evidence_type(value: str | None) -> str:
    # Delegate suffix-stripping to the model SSOT; degrade gracefully (rank 0 via .get)
    # for empty/unknown graph literals — this reader must never raise.
    return canonical_evidence_type_token(value) or ""


def _reconcile_evidence_vocab() -> None:
    """Fail-early gate: rank tables must stay in lock-step with the model enums."""
    if set(EVIDENCE_TYPE_RANK) | UNRANKED_EVIDENCE_TYPES != set(EvidenceType):
        raise ValueError(
            "EVIDENCE_TYPE_RANK | UNRANKED_EVIDENCE_TYPES must cover every EvidenceType; "
            f"got ranked={set(EVIDENCE_TYPE_RANK)} unranked={set(UNRANKED_EVIDENCE_TYPES)}"
        )
    if not set(EVIDENCE_TYPE_RANK).isdisjoint(UNRANKED_EVIDENCE_TYPES):
        raise ValueError("an unranked-by-design EvidenceType must not also be ranked")
    if set(EVIDENCE_ROLE_RANK) != set(EvidenceRole) - DIAGNOSTIC_ROLES:
        raise ValueError("EVIDENCE_ROLE_RANK must rank exactly the non-diagnostic EvidenceRoles")
    if set(STRENGTH_RANK) != set(EvidenceStrength):
        raise ValueError("STRENGTH_RANK must cover every EvidenceStrength")


_reconcile_evidence_vocab()


PROXY_STEP_PENALTY = 2          # gated proxy counts two ordinal steps lower (logic, not a cliff)
CURATION_STEP_PENALTY = 1       # reference (human-curated) dataset: one ordinal step lower (A2/A-D4)
DELTA_ENVELOPE = (0.3, 1.0)     # log-odds per ordinal step; OR ~1.35..2.72; SWEPT, not chosen
CONFIG_VERSION = "belief-logodds-v3"   # B2 committed dataset-derived independence; bump on any scoring input change


def type_steps(evidence_type: str | None) -> int:
    return max(0, EVIDENCE_TYPE_RANK.get(normalize_evidence_type(evidence_type), 0) - 1)


def role_steps(evidence_role: str | None) -> int:
    return max(0, EVIDENCE_ROLE_RANK.get(evidence_role or "", 0) - 1)


def strength_steps(strength: str | None) -> int:
    return max(0, STRENGTH_RANK.get(strength or "", 0) - 1)
