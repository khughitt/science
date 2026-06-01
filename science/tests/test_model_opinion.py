"""Tests for the subjective-logic opinion view (science_tool.model.opinion)."""
from __future__ import annotations

import pytest

from science_tool.model.opinion import opinion_from_scores


def test_masses_sum_to_one():
    for op in (opinion_from_scores(1, 0), opinion_from_scores(8, 2), opinion_from_scores(0, 0)):
        assert op.belief + op.disbelief + op.uncertainty == pytest.approx(1.0)


def test_uncertainty_falls_with_evidence():
    thin = opinion_from_scores(1, 0)
    rich = opinion_from_scores(8, 0)
    assert rich.uncertainty < thin.uncertainty


def test_no_evidence_is_maximal_ignorance():
    """No support, no dispute -> u = 1 (total ignorance), E = base_rate."""
    op = opinion_from_scores(0, 0)
    assert op.uncertainty == pytest.approx(1.0)
    assert op.expected == pytest.approx(op.base_rate)


def test_projected_probability():
    op = opinion_from_scores(8, 0)
    assert op.expected == pytest.approx(op.belief + op.base_rate * op.uncertainty)


def test_dispute_lowers_expected():
    assert opinion_from_scores(4, 4).expected < opinion_from_scores(8, 0).expected
