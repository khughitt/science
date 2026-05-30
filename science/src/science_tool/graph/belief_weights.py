"""Fixed ordinal rankings for evidence quality (design §2 rule 2, Phase 1).

Ordering is fixed here; per-project numeric weights and the quantitative scalar are
Phase 2 (opt-in via core/decisions.md). Unknown values rank 0 (degrade gracefully).
Canonical evidence_type values carry an '_evidence' suffix (cli.py:1646); we normalize.
"""
from __future__ import annotations

STANCE_SUPPORTS = "supports"
STANCE_DISPUTES = "disputes"

ROLE_DIRECT_TEST = "direct_test"
ROLE_PROXY_SUPPORT = "proxy_support"
ROLE_BACKGROUND = "background_constraint"
ROLE_NEGATIVE_CONTROL = "negative_control"
ROLE_MODEL_CRITICISM = "model_criticism"

INDEPENDENT = "independent"
SHARED_SOURCE = "shared-source"
CIRCULAR = "circular"

SCOPE_WHOLE_CLAIM = "whole_claim"
GATED_PROXY = frozenset({"indirect", "derived"})
DIAGNOSTIC_ROLES = frozenset({ROLE_NEGATIVE_CONTROL, ROLE_MODEL_CRITICISM})

_EVIDENCE_SUFFIX = "_evidence"

# Keyed on NORMALIZED (suffix-stripped) tokens.
EVIDENCE_TYPE_RANK = {
    "empirical_data": 4,
    "benchmark": 3,
    "simulation": 3,
    "literature": 2,
    "expert_judgment": 1,
}
EVIDENCE_ROLE_RANK = {ROLE_DIRECT_TEST: 3, ROLE_PROXY_SUPPORT: 2, ROLE_BACKGROUND: 1}
STRENGTH_RANK = {"strong": 3, "moderate": 2, "weak": 1}


def normalize_evidence_type(value: str | None) -> str:
    if not value:
        return ""
    return value[: -len(_EVIDENCE_SUFFIX)] if value.endswith(_EVIDENCE_SUFFIX) else value


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
