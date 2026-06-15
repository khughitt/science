"""Lifecycle-visibility predicate and classification guards (consolidation P1)."""

from __future__ import annotations

from science_tool.entities import (
    _HIDDEN_STATUSES,
    _LIVE_STATUSES,
    _STATUS_VALUES,
    is_default_visible,
)


def test_hidden_statuses_are_not_default_visible() -> None:
    assert is_default_visible("superseded") is False
    assert is_default_visible("archived") is False


def test_live_statuses_are_default_visible() -> None:
    assert is_default_visible("active") is True
    assert is_default_visible("proposed") is True
    assert is_default_visible("retired") is True  # retired stays visible in this slice
    assert is_default_visible("deprecated") is True
    assert is_default_visible("abandoned") is True


def test_missing_or_empty_status_is_default_visible() -> None:
    assert is_default_visible(None) is True
    assert is_default_visible("") is True
