"""Log-odds belief scalar (design §1/§2, Phase 2). Reads the reduced units that
aggregate_belief already produced; never re-derives independence."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .belief import BeliefMagnitude, BeliefResult, EvidenceUnit, is_proxy_gated
from .belief_weights import (
    CURATION_STEP_PENALTY, DELTA_ENVELOPE, PROXY_STEP_PENALTY, role_steps, strength_steps, type_steps,
)

_FEATURE_FLAG_BELIEF_SCALAR = re.compile(
    r"^-\s+\*\*Feature flag:\*\*\s*belief-scalar\s*$", re.MULTILINE
)


def unit_score(u: EvidenceUnit) -> int:
    s = type_steps(u.evidence_type) + role_steps(u.evidence_role) + strength_steps(u.strength)
    if is_proxy_gated(u):
        s = max(0, s - PROXY_STEP_PENALTY)
    if u.is_reference_dataset:
        s = max(0, s - CURATION_STEP_PENALTY)
    return s


# Step-equivalent weight of a maximally sign-confident posterior. One unit-score
# "step" ~ a single qualitative strength/role/type increment; a posterior at
# prob_sign == 1 contributes at most this many steps to the continuous band.
QUANT_MASS_STEPS = 2.0

# Polarity values that carry an authored sign to compare beta against.
_SIGNED_POLARITIES = frozenset({"positive", "negative"})


def _stance_oriented_mass(u: EvidenceUnit, magnitude: float) -> tuple[float, float]:
    """Return oriented mass using the authored stance (no beta comparison).

    Used for unsigned/absent polarity and for sign-meaningful polarity when the
    observed sign is not yet determined (beta==0, prob_sign absent, or prob_sign≤0.5).
    """
    if u.stance == "supports":
        return (magnitude, 0.0)
    return (0.0, magnitude)


def _oriented_quant_mass(u: EvidenceUnit) -> tuple[float, float]:
    """Return (support_mass, dispute_mass) the unit's posterior adds to the bands.

    The posterior contributes ONLY when a fitted ``beta`` and ``prob_sign`` are
    present. Support vs dispute is decided by comparing ``sign(beta)`` to the
    target proposition's authored polarity and the line's stance; the magnitude
    scales with ``prob_sign`` (sign confidence, NOT an independent stance).

    For sign-meaningful polarity (positive/negative), the contradiction check and
    sign-oriented routing apply ONLY when the sign is determined:
        sign_determined = beta != 0 and prob_sign > 0.5
    When the sign is undetermined (beta==0, prob_sign absent, or prob_sign≤0.5)
    the function falls back to stance orientation — no ValueError is raised.

    Raises ValueError when the authored stance contradicts a DETERMINED observed
    sign (supports ⇒ must match the claimed sign; disputes ⇒ must oppose it).
    """
    beta = u.quant_beta
    prob_sign = u.quant_prob_sign
    if beta is None or prob_sign is None:
        return (0.0, 0.0)

    magnitude = QUANT_MASS_STEPS * prob_sign
    polarity = u.target_polarity

    if polarity == "not_applicable":
        # Sign-less proposition: a signed beta has no oriented meaning.
        return (0.0, 0.0)

    if polarity not in _SIGNED_POLARITIES:
        # unsigned (or absent): no claimed sign to compare against.
        return _stance_oriented_mass(u, magnitude)

    # Sign-meaningful polarity. Only act on the sign when it is genuinely determined.
    sign_determined = (beta != 0) and (prob_sign > 0.5)

    if not sign_determined:
        # Sign is undetermined (zero beta, or prob_sign too low): fall back to stance.
        return _stance_oriented_mass(u, magnitude)

    # Determined sign: orient by sign(beta) vs polarity, raise on contradiction.
    observed_matches_claim = (beta > 0) if polarity == "positive" else (beta < 0)
    stance_asserts_match = u.stance == "supports"
    if observed_matches_claim != stance_asserts_match:
        raise ValueError(
            f"evidence-line {u.line_uri} stance={u.stance!r} contradicts its fitted "
            f"posterior: beta={beta} runs "
            f"{'with' if observed_matches_claim else 'against'} the target's "
            f"{polarity!r} polarity, but stance asserts the "
            f"{'opposite' if stance_asserts_match else 'matching'} sign. "
            "No override field is defined; refusing to assign oriented mass."
        )

    if observed_matches_claim:
        return (magnitude, 0.0)
    return (0.0, magnitude)


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
    # Ordinal integer scores (UNCHANGED): the qualitative headline + opinion inputs.
    s_score = sum(unit_score(u) for u in result.support_units)
    d_score = sum(unit_score(u) for u in result.dispute_units)
    # Oriented posterior contribution (Task 3a): a continuous shift of the bands
    # only — it never moves the ordinal scores or the magnitude. Contradictory
    # stance/beta combinations raise here, during belief computation.
    quant_support = 0.0
    quant_dispute = 0.0
    for unit in (*result.support_units, *result.dispute_units):
        qs, qd = _oriented_quant_mass(unit)
        quant_support += qs
        quant_dispute += qd
    s_mass = s_score + quant_support
    d_mass = d_score + quant_dispute
    net_lo = _t(d_lo * s_mass - d_hi * d_mass)   # support down, dispute up
    net_hi = _t(d_hi * s_mass - d_lo * d_mass)   # support up, dispute down
    net_robust = (net_lo > 0 and net_hi > 0) or (net_lo < 0 and net_hi < 0)
    diag_disputes = sum(1 for u in result.diagnostics if u.stance == "disputes")
    return BeliefScalar(
        massed_support_score=s_score,
        massed_dispute_score=d_score,
        massed_support_band=(_t(d_lo * s_mass), _t(d_hi * s_mass)),
        massed_dispute_band=(_t(d_lo * d_mass), _t(d_hi * d_mass)),
        net_band=(net_lo, net_hi),
        net_robust=net_robust,
        contested=result.contested,
        diagnostic_dispute_count=diag_disputes,
    )


def format_belief_weight(result: BeliefResult, scalar: BeliefScalar) -> dict[str, Any]:
    """Display contract (design §3): net annotates, never overrides, the ordinal headline."""
    ceiling_binds = result.magnitude == BeliefMagnitude.FRAGILE or result.capped_by_refutation
    notes: list[str] = []
    if result.magnitude == BeliefMagnitude.FRAGILE:
        notes.append("single-unit ceiling applies")
    if result.capped_by_refutation:
        notes.append("refutation cap applies")
    if not scalar.net_robust:
        notes.append("net not robust")
    if scalar.contested and scalar.massed_dispute_score == 0:
        notes.append("contested (diagnostic)")
    show_net = scalar.net_robust and not ceiling_binds
    return {
        "massed_support": list(scalar.massed_support_band),
        "massed_dispute": list(scalar.massed_dispute_band),
        "net": list(scalar.net_band) if show_net else None,
        "contested": scalar.contested,
        "diagnostic_dispute_count": scalar.diagnostic_dispute_count,
        "notes": notes,
    }


def belief_scalar_enabled(project_root: Path) -> bool:
    """True iff core/decisions.md has an ACTIVE decision carrying the belief-scalar flag.

    A missing project root or decisions file silently disables the feature (returns False).
    """
    # Imported lazily to keep the graph -> curate dependency localized (mirrors graph/health.py),
    # so importing belief_scalar for unit_score/belief_scalar does not pull in the curate chain.
    from science_tool.curate.agents_md import active_decision_sections

    decisions = project_root / "core" / "decisions.md"
    return any(
        _FEATURE_FLAG_BELIEF_SCALAR.search(body)
        for _id, body in active_decision_sections(decisions)
    )
