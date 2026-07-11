"""The InstrumentResult status invariant is ENFORCED, not documented.

`empty` and `unwired` are different, and the result cannot be constructed without
choosing between them. See docs/plans/2026-07-11-instrument-result-convergence-design.md.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_tool.instruments import InstrumentResult


def test_ok_requires_rows() -> None:
    with pytest.raises(ValidationError, match="requires non-empty rows"):
        InstrumentResult[int](status="ok", rows=[])


def test_empty_forbids_rows() -> None:
    with pytest.raises(ValidationError, match="forbids rows"):
        InstrumentResult[int](status="empty", rows=[1])


def test_unwired_forbids_rows() -> None:
    with pytest.raises(ValidationError, match="forbids rows"):
        InstrumentResult[int](status="unwired", rows=[1], code="x")


def test_unwired_requires_code() -> None:
    with pytest.raises(ValidationError, match="requires a machine-readable code"):
        InstrumentResult[int](status="unwired", rows=[])


def test_valid_constructions() -> None:
    assert InstrumentResult.ok([1, 2]).rows == [1, 2]
    assert InstrumentResult[int].empty().rows == []
    unwired = InstrumentResult[int].unwired(code="no_resolvable_topics", reason="none resolve")
    assert unwired.status == "unwired"
    assert unwired.code == "no_resolvable_topics"


def test_ok_may_carry_a_caveat() -> None:
    """A successful run can still have dropped part of its input (design: partial resolution)."""
    result = InstrumentResult.ok([1], code="partial_topic_resolution", reason="7 of 10 refs unresolved")
    assert result.status == "ok"
    assert result.reason == "7 of 10 refs unresolved"


def test_from_rows_never_infers_unwired() -> None:
    """from_rows is for instruments that DEFINITELY ran.

    An empty return through this door is `empty`, never `unwired` -- the decision
    must be made by the caller, never inferred from a row count. That inference is
    the exact bug this type exists to stop.
    """
    assert InstrumentResult[int].from_rows([]).status == "empty"
    assert InstrumentResult.from_rows([1]).status == "ok"
