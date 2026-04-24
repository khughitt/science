import math
from typing import Any

import numpy as np
import pytest

from h01_simulator.config import SimConfig
from h01_simulator.metrics import brier, recall, regret


def test_recall_perfect():
    truth = np.array([1, 1, 0, 0])
    post = np.array([0.9, 0.8, 0.1, 0.2])
    assert recall(truth, post, threshold=0.5) == 1.0


def test_recall_all_missed():
    truth = np.array([1, 1, 0, 0])
    post = np.array([0.1, 0.2, 0.3, 0.4])
    assert recall(truth, post, threshold=0.5) == 0.0


def test_recall_partial():
    truth = np.array([1, 1, 1, 0])
    post = np.array([0.9, 0.4, 0.8, 0.1])
    assert recall(truth, post, threshold=0.5) == pytest.approx(2 / 3)


def test_recall_nan_when_no_positives():
    truth = np.array([0, 0, 0])
    post = np.array([0.9, 0.9, 0.9])
    assert math.isnan(recall(truth, post, threshold=0.5))


def test_recall_threshold_inclusive():
    truth = np.array([1])
    post = np.array([0.5])
    assert recall(truth, post, threshold=0.5) == 1.0


def test_recall_threshold_sweep_via_posteriors():
    """A threshold sweep is an analysis-time operation using a single call per threshold."""
    truth = np.array([1, 1, 0, 0])
    post = np.array([0.9, 0.4, 0.3, 0.1])
    at_05 = recall(truth, post, threshold=0.5)
    at_03 = recall(truth, post, threshold=0.3)
    assert at_05 == 0.5
    assert at_03 == 1.0


def test_brier_perfect_is_zero():
    truth = np.array([1, 0, 1, 0])
    post = np.array([1.0, 0.0, 1.0, 0.0])
    assert brier(truth, post) == 0.0


def test_brier_max_miscalibration():
    truth = np.array([1, 0])
    post = np.array([0.0, 1.0])
    assert brier(truth, post) == 1.0


def test_brier_known_value():
    truth = np.array([1, 0])
    post = np.array([0.7, 0.3])
    # (0.7-1)^2 + (0.3-0)^2 → mean 0.09
    assert brier(truth, post) == pytest.approx(0.09)


def _sim(**overrides: Any) -> SimConfig:
    base: dict[str, Any] = dict(n_propositions=3, budget=6, p_pos=0.8, p_neg=0.2, prior_true=0.5)
    base.update(overrides)
    return SimConfig(**base)


def test_regret_oracle_allocation_is_zero():
    cfg = _sim()
    truth = np.array([1, 0, 0])
    bias_offsets = np.zeros(3)
    allocations = np.array([6, 0, 0])  # all budget on the best prop
    assert regret(truth, bias_offsets, allocations, cfg) == pytest.approx(0.0)


def test_regret_positive_when_budget_on_false_props():
    cfg = _sim()
    truth = np.array([1, 0, 0])
    bias_offsets = np.zeros(3)
    allocations = np.array([0, 3, 3])
    # oracle: 6 * 0.8 = 4.8; policy: 3*0.2 + 3*0.2 = 1.2; regret = 3.6
    assert regret(truth, bias_offsets, allocations, cfg) == pytest.approx(3.6)


def test_regret_uses_per_proposition_offsets():
    cfg = _sim()
    truth = np.array([1, 1, 0])
    # Proposition 1 is biased with offset -0.5 → effective p = 0.3
    bias_offsets = np.array([0.0, -0.5, 0.0])
    allocations = np.array([6, 0, 0])
    # best effective p = 0.8 (prop 0); oracle = 4.8; policy = 4.8; regret = 0
    assert regret(truth, bias_offsets, allocations, cfg) == pytest.approx(0.0)


def test_regret_clips_effective_probability_to_unit_interval():
    cfg = _sim(p_pos=0.9, p_neg=0.1)
    truth = np.array([1, 1, 0])
    # Offset of +0.5 would push p to 1.4; must clip to 1.0
    bias_offsets = np.array([0.5, 0.0, 0.0])
    allocations = np.array([6, 0, 0])
    # best = 1.0; oracle = 6.0; policy = 6.0; regret = 0
    assert regret(truth, bias_offsets, allocations, cfg) == pytest.approx(0.0)
