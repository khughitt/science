"""archived is a valid status on the consolidatable core kinds (P4)."""
from __future__ import annotations

import pytest

from science_tool.entities import (
    _HIDDEN_STATUSES,
    _LIVE_STATUSES,
    _STATUS_VALUES,
    valid_statuses,
)

CONSOLIDATABLE_KINDS = [
    "hypothesis", "question", "proposition", "observation", "finding",
    "interpretation", "synthesis", "report", "discussion", "inquiry",
    "mechanism", "theme", "topic", "method", "plan", "search", "decision",
    "evidence-line",
]


@pytest.mark.parametrize("kind", CONSOLIDATABLE_KINDS)
def test_consolidatable_kind_accepts_archived(kind: str) -> None:
    vs = valid_statuses(kind)
    assert vs is not None and "archived" in vs


def test_reference_kinds_do_not_gain_archived() -> None:
    for kind in ("paper", "book", "talk"):
        vs = valid_statuses(kind)
        assert vs is not None and "archived" not in vs


def test_every_declared_status_still_classified() -> None:
    classified = _LIVE_STATUSES | _HIDDEN_STATUSES
    declared = {s for statuses in _STATUS_VALUES.values() for s in statuses}
    assert declared - classified == set()
