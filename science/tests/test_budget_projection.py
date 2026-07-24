from __future__ import annotations

import pytest

from science_tool.budget.projection import project_rows

ROWS = [{"id": f"t{i:03d}"} for i in range(100)]


def test_projection_is_a_noop_under_the_cap() -> None:
    result = project_rows(ROWS[:5], max_rows=40)
    assert result.rows == ROWS[:5]
    assert (result.omitted, result.total, result.truncated) == (0, 5, False)


def test_projection_keeps_the_first_n_in_caller_order() -> None:
    result = project_rows(ROWS, max_rows=40)
    assert result.rows == ROWS[:40]
    assert (result.omitted, result.total, result.truncated) == (60, 100, True)


def test_none_cap_disables_row_projection() -> None:
    result = project_rows(ROWS, max_rows=None)
    assert result.rows == ROWS
    assert result.truncated is False


def test_empty_rows_project_cleanly() -> None:
    result = project_rows([], max_rows=40)
    assert (result.rows, result.total, result.truncated) == ([], 0, False)


def test_negative_cap_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_rows must be non-negative"):
        project_rows(ROWS, max_rows=-1)


def test_projection_is_generic_over_non_mapping_rows() -> None:
    """tasks list projects Task models, which are Pydantic BaseModels, not Mappings."""
    from datetime import date

    from science_model.tasks import Task

    tasks = [Task(id=f"t{i:03d}", title=f"Task {i}", created=date(2026, 1, 1)) for i in range(10)]
    result = project_rows(tasks, max_rows=4)
    assert len(result.rows) == 4
    assert all(isinstance(row, Task) for row in result.rows)
    assert result.total == 10
