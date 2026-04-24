"""End-of-run metrics for the h01 simulator."""

from __future__ import annotations

import math

import numpy as np


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
