"""Log-odds belief scalar (design §1/§2, Phase 2). Reads the reduced units that
aggregate_belief already produced; never re-derives independence."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from science_tool.curate.agents_md import active_decision_sections

from .belief import BeliefResult, EvidenceUnit, is_proxy_gated
from .belief_weights import (
    DELTA_ENVELOPE, PROXY_STEP_PENALTY, role_steps, strength_steps, type_steps,
)

_FEATURE_FLAG_BELIEF_SCALAR = re.compile(
    r"^-\s+\*\*Feature flag:\*\*\s*belief-scalar\s*$", re.MULTILINE
)


def unit_score(u: EvidenceUnit) -> int:
    s = type_steps(u.evidence_type) + role_steps(u.evidence_role) + strength_steps(u.strength)
    if is_proxy_gated(u):
        s = max(0, s - PROXY_STEP_PENALTY)
    return s


@dataclass(frozen=True)
class BeliefScalar:
    massed_support_score: int
    massed_dispute_score: int
    massed_support_band: tuple[float, float]
    massed_dispute_band: tuple[float, float]
    net_band: tuple[float, float]
    net_robust: bool
    contested: bool
    diagnostic_dispute_count: int


def _t(x: float) -> float:
    return round(math.tanh(0.5 * x), 6)


def belief_scalar(result: BeliefResult) -> BeliefScalar:
    d_lo, d_hi = DELTA_ENVELOPE
    s_score = sum(unit_score(u) for u in result.support_units)
    d_score = sum(unit_score(u) for u in result.dispute_units)
    net_lo = _t(d_lo * s_score - d_hi * d_score)   # support down, dispute up
    net_hi = _t(d_hi * s_score - d_lo * d_score)   # support up, dispute down
    net_robust = (net_lo > 0 and net_hi > 0) or (net_lo < 0 and net_hi < 0)
    diag_disputes = sum(1 for u in result.diagnostics if u.stance == "disputes")
    return BeliefScalar(
        massed_support_score=s_score,
        massed_dispute_score=d_score,
        massed_support_band=(_t(d_lo * s_score), _t(d_hi * s_score)),
        massed_dispute_band=(_t(d_lo * d_score), _t(d_hi * d_score)),
        net_band=(net_lo, net_hi),
        net_robust=net_robust,
        contested=result.contested,
        diagnostic_dispute_count=diag_disputes,
    )


def belief_scalar_enabled(project_root: Path) -> bool:
    """True iff core/decisions.md has an ACTIVE decision carrying the belief-scalar flag."""
    decisions = project_root / "core" / "decisions.md"
    return any(
        _FEATURE_FLAG_BELIEF_SCALAR.search(body)
        for _id, body in active_decision_sections(decisions)
    )
