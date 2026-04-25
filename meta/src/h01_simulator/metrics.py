"""End-of-run metrics for the h01 simulator.

Metric / oracle taxonomy
------------------------
Each metric implies a particular "best achievable" baseline (an oracle).
A policy that mimics one oracle may score badly on a metric defined against
a different oracle. Pick the metric matched to the claim under test and
read others as diagnostics, not corroboration.

- ``recall`` — fraction of truth-positives with ``posterior_mean >= threshold``.
  Already a gap-to-perfect (oracle recall is 1.0 when positives exist), so
  no separate "recall regret" is reported. A budget-aware recall oracle
  would be a meaningful companion metric but is deferred until interpretation
  needs it.
- ``brier`` — mean squared error of posterior mean against ground truth.
  Oracle is perfect calibration (mean = truth); reported directly, not as
  a regret.
- ``signal_count_regret`` — ``oracle - policy`` expected signal count, where
  the oracle allocates the whole budget to the proposition with the highest
  effective signal probability. WARNING: under ``bias_model="shared"`` at
  high noise, bias offsets can push a truth=0 proposition's effective
  probability above every truth=1, so this oracle targets a false
  proposition. A policy that mimics the oracle then scores
  ``signal_count_regret = 0`` and ``recall = 0`` — i.e. the metric
  decorrelates from recall in exactly the regime H01's disconfirmation route
  occupies. Treat as a diagnostic, NOT as recall corroboration in ``shared``
  rows.
"""

from __future__ import annotations

import math

import numpy as np

from .config import SimConfig


def recall(truth: np.ndarray, posterior_mean: np.ndarray, threshold: float = 0.5) -> float:
    """Fraction of truth=1 propositions with posterior_mean >= threshold.

    NaN when there are no ground-truth positives.
    """
    positives = truth == 1
    n_pos = int(positives.sum())
    if n_pos == 0:
        return math.nan
    predicted = posterior_mean >= threshold
    return float((positives & predicted).sum() / n_pos)


def brier(truth: np.ndarray, posterior_mean: np.ndarray) -> float:
    """Mean squared error of posterior mean vs binary ground truth."""
    return float(np.mean((posterior_mean - truth.astype(float)) ** 2))


def signal_count_regret(
    truth: np.ndarray,
    bias_offsets: np.ndarray,
    allocations: np.ndarray,
    config: SimConfig,
) -> float:
    """Oracle-minus-policy expected signal count over the run.

    Effective per-proposition signal probability is
    ``clip((p_pos if truth=1 else p_neg) + bias_offsets, 0, 1)``.
    Oracle allocates the whole budget to the highest-probability proposition.

    KNOWN LIMITATION: under ``bias_model="shared"`` at high noise, the oracle
    may target a truth=0 proposition whose bias-inflated effective probability
    exceeds every truth=1 proposition. In that regime this metric and recall
    decorrelate — see module docstring. Read as a diagnostic, not as recall
    corroboration in ``shared`` rows.
    """
    base = np.where(truth == 1, config.p_pos, config.p_neg)
    effective = np.clip(base + bias_offsets, 0.0, 1.0)
    total_budget = float(allocations.sum())
    oracle = float(effective.max()) * total_budget
    policy = float((effective * allocations).sum())
    return oracle - policy
