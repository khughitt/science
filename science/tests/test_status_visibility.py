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


def test_no_core_kind_defaults_to_a_hidden_status() -> None:
    """Guard 1: a hidden state can never be the status an entity is born with."""
    from science_tool.entities import _DEFAULT_STATUS

    offenders = {
        kind: status
        for kind, status in _DEFAULT_STATUS.items()
        if status in _HIDDEN_STATUSES
    }
    assert offenders == {}, f"kinds defaulting to a hidden status: {offenders}"


def test_every_declared_status_is_classified_live_or_hidden() -> None:
    """Guard 2: every status any kind declares must be in the live allowlist or the
    hidden set. An unclassified status would silently stay default-visible (since
    is_default_visible is a pure hidden-set check), so this fails loud to force a
    deliberate live-or-hidden decision."""
    classified = _LIVE_STATUSES | _HIDDEN_STATUSES
    declared = {status for statuses in _STATUS_VALUES.values() for status in statuses}
    unclassified = declared - classified
    assert unclassified == set(), (
        f"unclassified statuses (add to _LIVE_STATUSES or _HIDDEN_STATUSES): {sorted(unclassified)}"
    )


def test_live_and_hidden_sets_are_disjoint() -> None:
    assert _LIVE_STATUSES.isdisjoint(_HIDDEN_STATUSES)
