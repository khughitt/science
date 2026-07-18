"""Adjudication, Manski bounds, and the pre-registered gate (design §6-§7).

Written BEFORE the draw. A gate implemented after seeing data is tuned to data.
"""

from __future__ import annotations

from enum import StrEnum

from scipy.stats import beta

from science_tool.correspondence.adjudicate import Adjudicated
from science_tool.drift_sample.normalize import normalize_claim

THETA: float = 0.10        # materiality; predeclared convention, not a derived optimum
ALPHA: float = 0.05 / 3    # Bonferroni over exactly three looks
LADDER: tuple[int, ...] = (40, 80, 264)
CENSUS: int = 264


class GateOutcome(StrEnum):
    RULE_OUT = "rule_out"
    DEMONSTRATE = "demonstrate"
    CONTINUE = "continue"


def verdict(claimed: str, adjudicated: Adjudicated) -> bool | None:
    """True = mismatch, False = match, None = indeterminate."""
    if adjudicated is Adjudicated.INDETERMINATE:
        return None
    normalized = normalize_claim(claimed)
    if normalized is None:
        return None
    return normalized != adjudicated.value


def manski(verdicts: list[bool | None]) -> tuple[int, int]:
    """(k_lo, k_hi): indeterminates counted as matches, then as mismatches."""
    k = sum(1 for v in verdicts if v is True)
    unknown = sum(1 for v in verdicts if v is None)
    return k, k + unknown


def cp_lower(k: int, n: int, alpha: float) -> float:
    return 0.0 if k == 0 else float(beta.ppf(alpha, k, n - k + 1))


def cp_upper(k: int, n: int, alpha: float) -> float:
    return 1.0 if k == n else float(beta.ppf(1 - alpha, k + 1, n - k))


def gate(k: int, n: int) -> GateOutcome:
    if n not in LADDER:
        raise ValueError(f"n={n} is not a predeclared look; looks are {LADDER}")
    if n == CENSUS:
        # The population is observed, not estimated: no interval applies.
        return GateOutcome.RULE_OUT if k / n < THETA else GateOutcome.DEMONSTRATE
    if cp_upper(k, n, ALPHA) < THETA:
        return GateOutcome.RULE_OUT
    if cp_lower(k, n, ALPHA) > THETA:
        return GateOutcome.DEMONSTRATE
    return GateOutcome.CONTINUE
