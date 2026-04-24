"""End-of-run metrics for the h01 simulator."""

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


def regret(
    truth: np.ndarray,
    bias_offsets: np.ndarray,
    allocations: np.ndarray,
    config: SimConfig,
) -> float:
    """Oracle-minus-policy expected signal count over the run.

    Effective per-proposition signal probability is
    ``clip((p_pos if truth=1 else p_neg) + bias_offsets, 0, 1)``.
    Oracle allocates the whole budget to the highest-probability proposition.
    """
    base = np.where(truth == 1, config.p_pos, config.p_neg)
    effective = np.clip(base + bias_offsets, 0.0, 1.0)
    total_budget = float(allocations.sum())
    oracle = float(effective.max()) * total_budget
    policy = float((effective * allocations).sum())
    return oracle - policy
