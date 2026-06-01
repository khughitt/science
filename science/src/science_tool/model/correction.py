"""Latent-construct / measurement-model bias correction (RFC §8.1).

Treats an observed co-occurrence count as a **biased measurement** of a latent
association, the bias being marginal *attention* — how much each entity is observed
at all. With observed count ``C_ab`` between entities ``a`` and ``b``, marginals
``C_a.`` / ``C_.b``, and grand total ``N``::

    log E[C_ab] = log N + α_a + β_b + A_ab
    α_a = log(C_a. / N)      attention axis of a
    β_b = log(C_.b / N)      attention axis of b

The two-way independence null (``A_ab = 0``) is ``E0 = C_a.·C_.b / N``. The corrected
association is the log-scale residual — pointwise mutual information, the attention
axes **subtracted off**::

    PMI(a,b) = log(C_ab / E0) = log(C_ab·N / (C_a.·C_.b)) = log(C_ab/N) − α_a − β_b

    PMI > 0 : co-occurs MORE than attention predicts → specific association
    PMI ≈ 0 : explained by attention
    PMI < 0 : co-occurs LESS than attention predicts

``PPMI = max(PMI, 0)`` is the established debiased measure. This is the difference
between *correcting* the bias (subtracting the attention axis) and merely *flagging*
or *discounting* it: the per-entity attention vector ``α`` IS the latent nuisance
axis, and a low-rank factorization of the PPMI matrix is a shared latent COMMON
coordinate (see :mod:`science_tool.model.federation`).

These are pure scalar primitives. Applying PMI across a whole matrix and factorizing
it is data processing (numpy/scipy) and belongs to the consuming project, not the
framework.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def attention(marginal: float, grand_total: float) -> float:
    """The entity's attention axis: log(C_./N) (a log marginal share)."""
    return math.log(marginal / grand_total)


def pmi(cooc: float, marginal_a: float, marginal_b: float, grand_total: float) -> float | None:
    """Attention-subtracted association (PMI). ``None`` when there is no co-occurrence."""
    if cooc <= 0:
        return None
    return math.log((cooc * grand_total) / (marginal_a * marginal_b))


def ppmi(cooc: float, marginal_a: float, marginal_b: float, grand_total: float) -> float:
    """Positive PMI (``max(PMI, 0)``) — the standard debiased co-occurrence measure."""
    value = pmi(cooc, marginal_a, marginal_b, grand_total)
    return max(value, 0.0) if value is not None else 0.0


def is_specific(pmi_value: float | None) -> bool:
    """A correction-surviving association: co-occurs more than attention predicts."""
    return pmi_value is not None and pmi_value > 0.0


@dataclass(frozen=True)
class CorrectedAssociation:
    """One attention-corrected association (entity pair)."""

    key: str
    raw_count: int
    pmi: float | None

    @property
    def ppmi(self) -> float:
        return max(self.pmi, 0.0) if self.pmi is not None else 0.0

    @property
    def specific(self) -> bool:
        return is_specific(self.pmi)
