from __future__ import annotations

import pytest

from science_tool.budget.registry import (
    BUDGETS,
    DEFERRED,
    EXEMPTIONS,
    CommandBudget,
    PayloadShape,
    lookup,
    shape_for,
)

WIRED = ["tasks list", "health", "entities inventory", "data audit"]


@pytest.mark.parametrize("path", WIRED)
def test_slice_1a_commands_are_budgeted(path: str) -> None:
    budget = lookup(path)
    assert isinstance(budget, CommandBudget)
    assert budget.max_chars > 0


@pytest.mark.parametrize("path", WIRED)
def test_every_budgeted_command_declares_a_shape(path: str) -> None:
    assert isinstance(shape_for(path), PayloadShape)


def test_rows_shape_declares_a_row_cap() -> None:
    for path, budget in BUDGETS.items():
        if budget.shape is PayloadShape.ROWS:
            assert budget.max_rows is not None, f"{path} is row-shaped but has no max_rows"


def test_document_shape_declares_no_row_cap() -> None:
    """A versioned document is refused whole, never partially emitted."""
    for path, budget in BUDGETS.items():
        if budget.shape is PayloadShape.DOCUMENT:
            assert budget.max_rows is None


def test_lookup_returns_none_for_unregistered_command() -> None:
    assert lookup("tasks add") is None


def test_every_deferred_entry_states_what_makes_it_grow() -> None:
    """DEFERRED is defined by growability, not by current size.

    The reason string is the mirror of an exemption's: it is the claim being recorded,
    and it is what stops the table becoming a parking lot.
    """
    for path, entry in DEFERRED.items():
        assert entry.growth_reason.strip(), f"{path} is deferred with no growth reason"
        assert entry.target_slice.strip(), f"{path} is deferred with no target slice"


def test_a_growable_but_small_command_can_be_deferred() -> None:
    """autonomy path-gate emits one row per denial but measures tiny on most runs.

    It is not exempt (its output grows with the run's change set) and has no
    over-threshold measurement, so the taxonomy must still have a truthful home for it.
    Slice 1b-3 batch W1b wired the original example here (tasks archive) into BUDGETS.
    """
    entry = DEFERRED["autonomy path-gate"]
    assert entry.measured_chars is None
    assert entry.growth_reason.strip()


def test_tasks_summary_is_deferred_because_distinct_keys_make_it_grow() -> None:
    """Each arbitrary task type/group value adds a member to both output formats."""
    assert "tasks summary" not in EXEMPTIONS
    entry = DEFERRED["tasks summary"]
    assert entry.target_slice == "1b"
    assert "type" in entry.growth_reason
    assert "group" in entry.growth_reason


def test_the_three_tables_are_mutually_disjoint() -> None:
    assert not (set(BUDGETS) & set(EXEMPTIONS))
    assert not (set(BUDGETS) & set(DEFERRED))
    assert not (set(EXEMPTIONS) & set(DEFERRED))


def test_every_exemption_states_a_reason() -> None:
    for path, reason in EXEMPTIONS.items():
        assert reason.strip(), f"{path} is exempt with no reason"
