from typing import Any

import numpy as np
import pytest

from h01_simulator.config import PolicyConfig, SimConfig
from h01_simulator.sweep import run_single


def _sim(**overrides: Any) -> SimConfig:
    base: dict[str, Any] = dict(n_propositions=10, budget=50, p_pos=0.8, p_neg=0.2, prior_true=0.5, seed=0)
    base.update(overrides)
    return SimConfig(**base)


def test_run_single_returns_result_record_with_expected_shapes():
    r = run_single(_sim(), PolicyConfig(kind="thompson"))
    assert r.allocations.sum() == 50
    assert r.allocations.shape == (10,)
    assert r.final_posteriors.shape == (10, 2)
    assert r.ground_truth.shape == (10,)
    assert r.bias_offsets.shape == (10,)
    assert 0.0 <= r.brier <= 1.0
    # regret is non-negative within float tolerance
    assert r.regret >= -1e-9


def test_run_single_deterministic_given_seed():
    a = run_single(_sim(seed=42), PolicyConfig(kind="thompson"))
    b = run_single(_sim(seed=42), PolicyConfig(kind="thompson"))
    assert np.array_equal(a.allocations, b.allocations)
    assert np.array_equal(a.final_posteriors, b.final_posteriors)
    assert np.array_equal(a.ground_truth, b.ground_truth)
    assert a.recall == b.recall or (np.isnan(a.recall) and np.isnan(b.recall))
    assert a.brier == b.brier


@pytest.mark.parametrize("kind", ["hard_gate", "constant_revisit", "thompson"])
def test_run_single_dispatches_every_policy_kind(kind):
    r = run_single(
        _sim(),
        PolicyConfig(kind=kind, warmup_actions=1, revisit_prob=0.1),
    )
    assert r.allocations.sum() == 50


def test_run_single_respects_configured_prior():
    sim = _sim(prior_alpha=5.0, prior_beta=5.0, budget=0)
    r = run_single(sim, PolicyConfig(kind="thompson"))
    # With budget=0 no observations happen; posteriors stay at the prior.
    assert np.allclose(r.final_posteriors[:, 0], 5.0)
    assert np.allclose(r.final_posteriors[:, 1], 5.0)


def test_run_single_integrates_with_shared_bias():
    sim = _sim(bias_model="shared", bias_fraction=0.3, bias_sigma=0.3, seed=1)
    r = run_single(sim, PolicyConfig(kind="thompson"))
    # Smoke: run terminates, shapes are correct, at least some bias offsets non-zero.
    assert r.allocations.sum() == 50
    assert r.bias_offsets.shape == (10,)
    assert np.count_nonzero(r.bias_offsets) >= 1
