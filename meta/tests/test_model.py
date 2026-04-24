import numpy as np
import pytest

from h01_simulator.config import SimConfig
from h01_simulator.model import Propositions, generate_propositions


def _cfg(**overrides) -> SimConfig:
    base = dict(
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
