"""Allocation policies for the h01 simulator.

Each factory returns a callable ``policy(model, action_idx, rng) -> int``
that picks the next proposition index to sample.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from .config import PolicyConfig
from .model import SignalModel

Policy = Callable[[SignalModel, int, np.random.Generator], int]


def hard_gate_policy(config: PolicyConfig) -> Policy:
    """Round-robin warm-up; then uniform over propositions >= threshold."""

    def policy(model: SignalModel, action_idx: int, rng: np.random.Generator) -> int:
        n = len(model.alpha)
        warmup_total = config.warmup_actions * n
        if action_idx < warmup_total:
            return action_idx % n
        means = model.posterior_mean()
        eligible = np.where(means >= config.gate_threshold)[0]
        if len(eligible) == 0:
            return int(rng.integers(n))
        return int(rng.choice(eligible))

    return policy


def constant_revisit_policy(config: PolicyConfig) -> Policy:
    """Hard-gate variant that samples the gated set with probability r."""

    def policy(model: SignalModel, action_idx: int, rng: np.random.Generator) -> int:
        n = len(model.alpha)
        warmup_total = config.warmup_actions * n
        if action_idx < warmup_total:
            return action_idx % n
        means = model.posterior_mean()
        eligible = np.where(means >= config.gate_threshold)[0]
        gated = np.where(means < config.gate_threshold)[0]
        if len(gated) > 0 and rng.random() < config.revisit_prob:
            return int(rng.choice(gated))
        if len(eligible) == 0:
            return int(rng.choice(gated)) if len(gated) > 0 else int(rng.integers(n))
        return int(rng.choice(eligible))

    return policy


def thompson_policy(config: PolicyConfig) -> Policy:
    """Sample one Beta draw per proposition; choose the argmax.

    Exploration pressure comes from posterior width; an explicit warmup
    round-robins to avoid degenerate draws under Beta(1, 1).
    """

    def policy(model: SignalModel, action_idx: int, rng: np.random.Generator) -> int:
        n = len(model.alpha)
        warmup_total = config.warmup_actions * n
        if action_idx < warmup_total:
            return action_idx % n
        samples = rng.beta(model.alpha, model.beta)
        return int(np.argmax(samples))

    return policy


POLICIES: dict[str, Callable[[PolicyConfig], Policy]] = {
    "hard_gate": hard_gate_policy,
    "constant_revisit": constant_revisit_policy,
    "thompson": thompson_policy,
}
