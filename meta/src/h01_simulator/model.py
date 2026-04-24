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


class SignalModel:
    """Beta-Bernoulli model over a set of propositions.

    Per-proposition posterior parameters are initialised to
    (config.prior_alpha, config.prior_beta). The effective signal
    probability for proposition i is
    ``clip(p_pos if truth[i] else p_neg) + bias_offsets[i], 0, 1)``.
    """

    def __init__(
        self,
        propositions: Propositions,
        config: SimConfig,
        rng: np.random.Generator,
    ) -> None:
        self.props = propositions
        self.config = config
        self.rng = rng
        n = len(propositions.truth)
        self.alpha = np.full(n, config.prior_alpha, dtype=np.float64)
        self.beta = np.full(n, config.prior_beta, dtype=np.float64)

    def _effective_p(self, i: int) -> float:
        base = self.config.p_pos if self.props.truth[i] == 1 else self.config.p_neg
        return float(np.clip(base + self.props.bias_offsets[i], 0.0, 1.0))

    def sample_signal(self, i: int) -> int:
        return int(self.rng.random() < self._effective_p(i))

    def observe(self, i: int, signal: int) -> None:
        if signal == 1:
            self.alpha[i] += 1.0
        else:
            self.beta[i] += 1.0

    def posterior_mean(self) -> np.ndarray:
        return self.alpha / (self.alpha + self.beta)

    def posterior_var(self) -> np.ndarray:
        a = self.alpha
        b = self.beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1.0))

    def sample_thompson(self) -> np.ndarray:
        return self.rng.beta(self.alpha, self.beta)
