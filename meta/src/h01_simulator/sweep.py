"""Run orchestration and sweep runner for the h01 simulator."""

from __future__ import annotations

import numpy as np

from .config import PolicyConfig, RunResult, SimConfig
from .metrics import brier, recall, regret
from .model import SignalModel, generate_propositions
from .policies import POLICIES


def run_single(sim_config: SimConfig, policy_config: PolicyConfig) -> RunResult:
    """Execute one simulation run."""
    rng = np.random.default_rng(sim_config.seed)
    props = generate_propositions(sim_config, rng)
    model = SignalModel(props, sim_config, rng)
    policy_fn = POLICIES[policy_config.kind](policy_config)

    allocations = np.zeros(sim_config.n_propositions, dtype=int)
    for action_idx in range(sim_config.budget):
        i = policy_fn(model, action_idx, rng)
        signal = model.sample_signal(i)
        model.observe(i, signal)
        allocations[i] += 1

    post_mean = model.posterior_mean()
    return RunResult(
        config=sim_config,
        policy=policy_config,
        recall=recall(props.truth, post_mean),
        brier=brier(props.truth, post_mean),
        regret=regret(props.truth, props.bias_offsets, allocations, sim_config),
        allocations=allocations,
        final_posteriors=np.stack([model.alpha, model.beta], axis=1),
        ground_truth=props.truth,
        bias_offsets=props.bias_offsets,
    )
