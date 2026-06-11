"""Ordered projection from canonical derived belief fields to a 5-band edge status.

Order (first match wins):
  1. eliminated  — refuted is truthy
  2. unknown     — no grounding evidence (ordered BEFORE structural)
  3. structural  — claim_layer == "structural_claim" (with grounding)
  4. supported   — belief_magnitude in {"supported", "well_supported"}
  5. tentative   — default fallback
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DerivedEdgeStatus:
    """Immutable result of the derived_edge_status projection."""

    status: str
    reason: str


_SUPPORTED_MAGNITUDES = {"supported", "well_supported"}


def derived_edge_status(
    *,
    belief_magnitude: str,
    refuted: bool,
    claim_layer: str,
    has_grounding_evidence: bool,
) -> DerivedEdgeStatus:
    """Project canonical derived belief fields to a single ordered 5-band status.

    Parameters
    ----------
    belief_magnitude:
        String magnitude band (e.g. ``"supported"``, ``"well_supported"``,
        ``"fragile"``, ``"speculative"``).
    refuted:
        Truthy if any refutation evidence exists for this edge.
    claim_layer:
        The claim layer string (e.g. ``"causal_effect"``, ``"structural_claim"``).
    has_grounding_evidence:
        True when at least one grounding evidence line is attached.

    Returns
    -------
    DerivedEdgeStatus
        Frozen dataclass with ``status`` (one of ``eliminated``, ``unknown``,
        ``structural``, ``supported``, ``tentative``) and ``reason`` naming the
        rule that fired.

    Notes
    -----
    ``contested`` is NOT an input here — it is a separate overlay computed
    elsewhere and must not be folded into this ordinal.
    """
    if refuted:
        return DerivedEdgeStatus(status="eliminated", reason="refuted")

    if not has_grounding_evidence:
        return DerivedEdgeStatus(status="unknown", reason="no grounding evidence")

    if claim_layer == "structural_claim":
        return DerivedEdgeStatus(status="structural", reason="structural claim with grounding")

    if belief_magnitude in _SUPPORTED_MAGNITUDES:
        return DerivedEdgeStatus(status="supported", reason="belief magnitude supported/well_supported")

    return DerivedEdgeStatus(status="tentative", reason="default: tentative")
