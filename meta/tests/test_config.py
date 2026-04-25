import numpy as np
import pytest

from h01_simulator.config import PolicyConfig, RunResult, SimConfig


def test_sim_config_defaults():
    cfg = SimConfig(n_propositions=10, budget=100, p_pos=0.7, p_neg=0.3, prior_true=0.5)
    assert cfg.prior_alpha == 1.0
    assert cfg.prior_beta == 1.0
    assert cfg.bias_model == "none"
    assert cfg.bias_fraction == 0.0
    assert cfg.bias_sigma == 0.0
    assert cfg.seed == 0


def test_sim_config_rejects_ordering_violation():
    with pytest.raises(ValueError):
        SimConfig(n_propositions=10, budget=100, p_pos=0.3, p_neg=0.7, prior_true=0.5)


def test_sim_config_rejects_out_of_range_probs():
    with pytest.raises(ValueError):
        SimConfig(n_propositions=10, budget=100, p_pos=1.2, p_neg=0.1, prior_true=0.5)


def test_sim_config_rejects_invalid_bias_model():
    with pytest.raises(ValueError):
        SimConfig(
            n_propositions=10,
            budget=100,
            p_pos=0.7,
            p_neg=0.3,
            prior_true=0.5,
            bias_model="garbage",  # type: ignore[arg-type]
        )


def test_sim_config_rejects_negative_bias_sigma():
    with pytest.raises(ValueError):
        SimConfig(
            n_propositions=10,
            budget=100,
            p_pos=0.7,
            p_neg=0.3,
            prior_true=0.5,
            bias_sigma=-0.1,
        )


def test_sim_config_rejects_nonpositive_prior_params():
    with pytest.raises(ValueError):
        SimConfig(
            n_propositions=10,
            budget=100,
            p_pos=0.7,
            p_neg=0.3,
            prior_true=0.5,
            prior_alpha=0.0,
        )


def test_policy_config_kind_allowed():
    PolicyConfig(kind="hard_gate")
    PolicyConfig(kind="constant_revisit", revisit_prob=0.1)
    PolicyConfig(kind="thompson")
    with pytest.raises(ValueError):
        PolicyConfig(kind="ucb")  # type: ignore[arg-type]


def test_policy_config_rejects_nonpositive_warmup():
    with pytest.raises(ValueError):
        PolicyConfig(kind="hard_gate", warmup_actions=0)
    with pytest.raises(ValueError):
        PolicyConfig(kind="hard_gate", warmup_actions=-1)


def test_policy_config_rejects_degenerate_gate_threshold():
    PolicyConfig(kind="hard_gate", gate_threshold=0.5)  # valid
    with pytest.raises(ValueError):
        PolicyConfig(kind="hard_gate", gate_threshold=0.0)
    with pytest.raises(ValueError):
        PolicyConfig(kind="hard_gate", gate_threshold=1.0)
    with pytest.raises(ValueError):
        PolicyConfig(kind="hard_gate", gate_threshold=1.5)


def test_run_result_carries_arrays():
    sim = SimConfig(n_propositions=3, budget=10, p_pos=0.8, p_neg=0.2, prior_true=0.5)
    pol = PolicyConfig(kind="hard_gate")
    r = RunResult(
        config=sim,
        policy=pol,
        recall=0.5,
        brier=0.25,
        signal_count_regret=1.0,
        allocations=np.array([3, 4, 3]),
        final_posteriors=np.ones((3, 2)),
        ground_truth=np.array([1, 0, 1]),
        bias_offsets=np.zeros(3),
    )
    assert r.allocations.sum() == 10
    assert r.bias_offsets.shape == (3,)
