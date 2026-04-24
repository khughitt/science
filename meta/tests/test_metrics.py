import math

import numpy as np
import pytest

from h01_simulator.metrics import brier, recall


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
