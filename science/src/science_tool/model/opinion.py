"""Subjective-logic opinion — an uncertainty-bearing derived view over belief scores.

A binomial subjective-logic opinion is the tuple (belief, disbelief, uncertainty,
base_rate) with belief + disbelief + uncertainty == 1. Its load-bearing feature is
the explicit **uncertainty mass** ``u`` — the ignorance the ordinal/log-odds belief
scalar cannot name. It is computed AS A DERIVED VIEW from the same post-reduction
support/dispute scores ``belief_scalar`` already produces; it does not fork the core
aggregation.

Mapping (Jøsang's evidential form): with positive evidence ``r``, negative evidence
``s``, non-informative prior weight ``W``, and base rate ``a``::

    b = r / (r + s + W)
    d = s / (r + s + W)
    u = W / (r + s + W)
    E = b + a * u            (the projected probability)

``r`` and ``s`` are the massed (post-reduction) support / dispute scores. The
``unit_score`` machinery already bakes in provenance honesty (gated-proxy and
curation step penalties), so a thinly-supported or discounted claim yields small
``r`` and hence large ``u`` (high, honest ignorance).

Status: this view is the *default-next* uncertainty representation (RFC §12.3), not
a settled successor to the belief scalar. The mapping rests on explicit assumptions
— ``W=2``, ``base_rate=0.5``, and treating ordinal support scores as evidential
counts — that a calibration study must still test.
"""
from __future__ import annotations

from dataclasses import dataclass

PRIOR_WEIGHT = 2.0       # W: non-informative prior mass (uniform Beta(1,1) -> a=0.5)


@dataclass(frozen=True)
class Opinion:
    belief: float
    disbelief: float
    uncertainty: float
    base_rate: float

    @property
    def expected(self) -> float:
        """Projected probability E = b + a*u."""
        return self.belief + self.base_rate * self.uncertainty

    def as_dict(self) -> dict[str, float]:
        return {
            "belief": round(self.belief, 4),
            "disbelief": round(self.disbelief, 4),
            "uncertainty": round(self.uncertainty, 4),
            "base_rate": round(self.base_rate, 4),
            "expected": round(self.expected, 4),
        }


def opinion_from_scores(
    support_score: float,
    dispute_score: float,
    base_rate: float = 0.5,
    prior_weight: float = PRIOR_WEIGHT,
) -> Opinion:
    """Derive a subjective-logic opinion from massed support/dispute scores."""
    denom = support_score + dispute_score + prior_weight
    return Opinion(
        belief=support_score / denom,
        disbelief=dispute_score / denom,
        uncertainty=prior_weight / denom,
        base_rate=base_rate,
    )
