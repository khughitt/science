from typing import Any

import numpy as np
import pytest

from h01_simulator.config import SimConfig
from h01_simulator.model import Propositions, SignalModel, generate_propositions


def _cfg(**overrides: Any) -> SimConfig:
    base: dict[str, Any] = dict(
        n_propositions=100,
        budget=100,
        p_pos=0.8,
        p_neg=0.2,
        prior_true=0.5,
    )
    base.update(overrides)
    return SimConfig(**base)


def test_generate_propositions_shapes():
    cfg = _cfg()
    props = generate_propositions(cfg, np.random.default_rng(0))
    assert isinstance(props, Propositions)
    assert props.truth.shape == (100,)
    assert props.bias_mask.shape == (100,)
    assert props.bias_offsets.shape == (100,)
    assert set(np.unique(props.truth).tolist()) <= {0, 1}
    assert set(np.unique(props.bias_mask).tolist()) <= {0, 1}


def test_generate_propositions_deterministic_given_seed():
    cfg = _cfg()
    a = generate_propositions(cfg, np.random.default_rng(42))
    b = generate_propositions(cfg, np.random.default_rng(42))
    assert np.array_equal(a.truth, b.truth)
    assert np.array_equal(a.bias_mask, b.bias_mask)
    assert np.array_equal(a.bias_offsets, b.bias_offsets)


def test_generate_propositions_prior_true_approx():
    cfg = _cfg(n_propositions=10_000, prior_true=0.3)
    props = generate_propositions(cfg, np.random.default_rng(0))
    assert 0.27 <= props.truth.mean() <= 0.33


def test_bias_model_none_produces_zero_offsets():
    cfg = _cfg(bias_model="none", bias_fraction=0.5, bias_sigma=1.0)
    props = generate_propositions(cfg, np.random.default_rng(0))
    assert np.all(props.bias_offsets == 0.0)
    assert props.bias_mask.sum() == 0


def test_bias_model_independent_has_varied_offsets():
    cfg = _cfg(
        n_propositions=100,
        bias_model="independent",
        bias_fraction=0.5,
        bias_sigma=0.3,
    )
    props = generate_propositions(cfg, np.random.default_rng(0))
    biased = props.bias_offsets[props.bias_mask == 1]
    assert len(biased) == 50
    # With iid Normal(0, 0.3) draws, standard deviation should be near 0.3
    # and the set of offsets should have more than one unique value.
    assert len(np.unique(biased)) > 10
    assert 0.15 <= biased.std() <= 0.45


def test_bias_model_shared_has_single_offset_in_subset():
    cfg = _cfg(
        n_propositions=100,
        bias_model="shared",
        bias_fraction=0.3,
        bias_sigma=0.3,
    )
    props = generate_propositions(cfg, np.random.default_rng(0))
    biased = props.bias_offsets[props.bias_mask == 1]
    assert len(biased) == 30
    # All biased offsets are the same draw.
    assert len(np.unique(biased)) == 1
    # Unbiased offsets are all zero.
    assert np.all(props.bias_offsets[props.bias_mask == 0] == 0.0)


def test_bias_fraction_zero_means_no_bias_even_with_active_model():
    cfg = _cfg(bias_model="shared", bias_fraction=0.0, bias_sigma=0.3)
    props = generate_propositions(cfg, np.random.default_rng(0))
    assert props.bias_mask.sum() == 0
    assert np.all(props.bias_offsets == 0.0)


def _make_model(truth, bias_offsets, cfg_overrides=None):
    overrides = dict(n_propositions=len(truth))
    if cfg_overrides:
        overrides.update(cfg_overrides)
    cfg = _cfg(**overrides)
    props = Propositions(
        truth=np.asarray(truth, dtype=np.int8),
        bias_mask=(np.asarray(bias_offsets) != 0.0).astype(np.int8),
        bias_offsets=np.asarray(bias_offsets, dtype=np.float64),
    )
    return SignalModel(props, cfg, np.random.default_rng(0)), cfg, props


def test_signal_model_initialises_with_configured_prior():
    cfg = _cfg(n_propositions=4, prior_alpha=2.0, prior_beta=3.0)
    props = generate_propositions(cfg, np.random.default_rng(0))
    m = SignalModel(props, cfg, np.random.default_rng(0))
    assert np.allclose(m.alpha, 2.0)
    assert np.allclose(m.beta, 3.0)


def test_signal_sample_frequency_matches_unbiased_rate():
    m, _, _ = _make_model([1, 0], [0.0, 0.0], cfg_overrides=dict(p_pos=0.9, p_neg=0.1))
    m.rng = np.random.default_rng(123)
    freq_true = np.mean([m.sample_signal(0) for _ in range(4000)])
    freq_false = np.mean([m.sample_signal(1) for _ in range(4000)])
    assert 0.87 <= freq_true <= 0.93
    assert 0.07 <= freq_false <= 0.13


def test_signal_bias_offset_shifts_rate():
    m, _, _ = _make_model([1], [-0.3], cfg_overrides=dict(p_pos=0.9, p_neg=0.1))
    m.rng = np.random.default_rng(123)
    freq = np.mean([m.sample_signal(0) for _ in range(4000)])
    # effective p = clip(0.9 - 0.3, 0, 1) = 0.6
    assert 0.57 <= freq <= 0.63


def test_observe_updates_alpha_beta_relative_to_prior():
    cfg = _cfg(n_propositions=3, prior_alpha=2.0, prior_beta=2.0)
    props = generate_propositions(cfg, np.random.default_rng(0))
    m = SignalModel(props, cfg, np.random.default_rng(0))
    m.observe(0, 1)
    m.observe(0, 1)
    m.observe(1, 0)
    assert m.alpha[0] == 4.0
    assert m.beta[0] == 2.0
    assert m.alpha[1] == 2.0
    assert m.beta[1] == 3.0


def test_posterior_mean_and_variance_match_beta_formula():
    cfg = _cfg(n_propositions=5, prior_alpha=1.0, prior_beta=1.0)
    props = generate_propositions(cfg, np.random.default_rng(0))
    m = SignalModel(props, cfg, np.random.default_rng(0))
    assert np.allclose(m.posterior_mean(), 0.5)
    assert np.allclose(m.posterior_var(), 1.0 / 12.0)


def test_sample_thompson_returns_valid_draws():
    cfg = _cfg(n_propositions=4)
    props = generate_propositions(cfg, np.random.default_rng(0))
    m = SignalModel(props, cfg, np.random.default_rng(0))
    samples = m.sample_thompson()
    assert samples.shape == (4,)
    assert np.all((samples >= 0.0) & (samples <= 1.0))


def test_observe_rejects_invalid_signal():
    cfg = _cfg(n_propositions=2)
    props = generate_propositions(cfg, np.random.default_rng(0))
    m = SignalModel(props, cfg, np.random.default_rng(0))
    with pytest.raises(ValueError):
        m.observe(0, 2)
    with pytest.raises(ValueError):
        m.observe(0, -1)
