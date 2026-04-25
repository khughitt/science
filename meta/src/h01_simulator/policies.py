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


def ucb_policy(config: PolicyConfig) -> Policy:
    """UCB1 exploration: argmax(posterior_mean + c * sqrt(log(t + 1) / n_i)).

    After a round-robin warmup phase, selects the arm with the highest upper
    confidence bound. Per-arm pull counts start at zero and are tracked
    incrementally in closure state. The array is sized on the first call since
    ``n_propositions`` is not known at factory time. One factory call per run in
    ``run_single`` ensures state resets between runs.
    """
    pulls: np.ndarray = np.empty(0, dtype=np.int64)

    def policy(model: SignalModel, action_idx: int, rng: np.random.Generator) -> int:
        nonlocal pulls
        n = len(model.alpha)
        if pulls.size == 0:
            pulls = np.zeros(n, dtype=np.int64)
        warmup_total = config.warmup_actions * n
        if action_idx < warmup_total:
            i = action_idx % n
        else:
            bonus = config.ucb_c * np.sqrt(np.log(action_idx + 1) / np.maximum(pulls, 1))
            score = model.posterior_mean() + bonus
            i = int(np.argmax(score))
        pulls[i] += 1
        return i

    return policy


POLICIES: dict[str, Callable[[PolicyConfig], Policy]] = {
    "hard_gate": hard_gate_policy,
    "constant_revisit": constant_revisit_policy,
    "thompson": thompson_policy,
    "ucb": ucb_policy,
}
