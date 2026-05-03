"""Unit tests for EntityClass and EpistemicReviewState."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from science_model.entities import EntityClass, EpistemicReviewState


def test_entity_class_values():
    assert EntityClass.EPISTEMIC.value == "epistemic"
    assert EntityClass.OPERATIONAL.value == "operational"
    assert EntityClass.REFERENCE.value == "reference"


def test_review_state_defaults():
    rs = EpistemicReviewState()
    assert rs.last_reviewed is None
    assert rs.last_review_note == ""
    assert rs.review_horizon_days is None


def test_review_state_with_values():
    rs = EpistemicReviewState(
        last_reviewed=date(2026, 5, 1),
        last_review_note="Re-checked after Lee2026 dataset added",
        review_horizon_days=90,
    )
    assert rs.last_reviewed == date(2026, 5, 1)
    assert rs.last_review_note == "Re-checked after Lee2026 dataset added"
    assert rs.review_horizon_days == 90


def test_review_state_rejects_negative_horizon():
    with pytest.raises(ValidationError, match="review_horizon_days"):
        EpistemicReviewState(review_horizon_days=-1)


def test_review_state_rejects_zero_horizon():
    with pytest.raises(ValidationError, match="review_horizon_days"):
        EpistemicReviewState(review_horizon_days=0)
