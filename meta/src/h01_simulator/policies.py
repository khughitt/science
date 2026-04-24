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


POLICIES: dict[str, Callable[[PolicyConfig], Policy]] = {
    "hard_gate": hard_gate_policy,
}
