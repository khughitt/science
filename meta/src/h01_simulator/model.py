"""Beta-Bernoulli signal model for the h01 simulator."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import SimConfig


@dataclass(frozen=True)
class Propositions:
    """Ground-truth labels, bias mask, and per-proposition bias offsets.

    ``bias_offsets[i]`` is the shift applied to proposition i's effective
    signal probability. It is zero where ``bias_mask[i] == 0``. The joint
    distribution of offsets across the biased subset encodes the bias
    model (independent vs shared).
    """

    truth: np.ndarray
    bias_mask: np.ndarray
    bias_offsets: np.ndarray


def generate_propositions(config: SimConfig, rng: np.random.Generator) -> Propositions:
    """Sample truth labels, choose a bias subset, and realise per-proposition offsets.

    - truth: iid Bernoulli(prior_true).
    - bias subset: a uniformly random subset of size round(bias_fraction * n).
    - offsets:
        none → all zero.
        independent → iid Normal(0, bias_sigma) for each member of the subset.
        shared → a single Normal(0, bias_sigma) draw applied to every member.
      Offsets outside the subset are zero in all modes.
    """
    n = config.n_propositions
    truth = (rng.random(n) < config.prior_true).astype(np.int8)
    bias_mask = np.zeros(n, dtype=np.int8)
    bias_offsets = np.zeros(n, dtype=np.float64)

    n_biased = int(round(config.bias_fraction * n))
    if n_biased > 0 and config.bias_model != "none" and config.bias_sigma > 0.0:
        idx = rng.permutation(n)[:n_biased]
        bias_mask[idx] = 1
        if config.bias_model == "independent":
            bias_offsets[idx] = rng.normal(0.0, config.bias_sigma, size=n_biased)
        else:  # "shared"
            delta = float(rng.normal(0.0, config.bias_sigma))
            bias_offsets[idx] = delta

    return Propositions(truth=truth, bias_mask=bias_mask, bias_offsets=bias_offsets)
