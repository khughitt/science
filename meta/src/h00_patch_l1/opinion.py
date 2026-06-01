# science:code
# status: library
# task_ids: [t065]
# science:end
"""Experimental subjective-logic opinion view (RFC §4, fork §12.3).

A binomial subjective-logic opinion is the tuple (belief, disbelief, uncertainty,
base_rate) with belief + disbelief + uncertainty == 1. Its load-bearing feature
is the explicit **uncertainty mass** `u` — the ignorance the log-odds scalar
cannot name. This is computed AS A DERIVED VIEW from the same post-reduction
support/dispute scores the shipped `belief_scalar` already produces (it does NOT
fork the core aggregation — exactly the "derived view, behind a flag" framing the
RFC recommends over a v4 successor).

Mapping (Jøsang's evidential form): with positive evidence r, negative evidence s,
non-informative prior weight W=2, and base rate a:

    b = r / (r + s + W)
    d = s / (r + s + W)
    u = W / (r + s + W)
    E = b + a * u           (the projected probability)

r and s are the massed (post-reduction) support / dispute scores. The shipped
`unit_score` already bakes in provenance honesty — gated-proxy and curation step
penalties — so an editorial-only label, or a discounted publication-gravity unit,
yields small r, hence large u (high, honest ignorance).
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
    denom = support_score + dispute_score + prior_weight
    return Opinion(
        belief=support_score / denom,
        disbelief=dispute_score / denom,
        uncertainty=prior_weight / denom,
        base_rate=base_rate,
    )
