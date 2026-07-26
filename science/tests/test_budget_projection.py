from __future__ import annotations

import pytest

from science_tool.budget.projection import project_rows, project_single_list_report

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


def test_single_list_report_caps_the_list_and_passes_summary_through() -> None:
    payload = {"summary": {"total": 100, "errors": 3}, "findings": ROWS}
    out = project_single_list_report(payload, "findings", cap=40)
    assert out["findings"] == ROWS[:40]
    assert out["findings_omitted"] == 60
    # summary is passed through unchanged -- never recomputed from the capped list
    assert out["summary"] == {"total": 100, "errors": 3}


def test_single_list_report_records_zero_omitted_under_the_cap() -> None:
    out = project_single_list_report({"findings": ROWS[:5]}, "findings", cap=40)
    assert out["findings"] == ROWS[:5]
    assert out["findings_omitted"] == 0


def test_single_list_report_does_not_mutate_the_input_payload() -> None:
    payload = {"findings": ROWS}
    project_single_list_report(payload, "findings", cap=10)
    assert payload["findings"] is ROWS and len(payload["findings"]) == 100


def test_single_list_report_rejects_a_missing_key() -> None:
    with pytest.raises(KeyError, match="hits"):
        project_single_list_report({"findings": ROWS}, "hits", cap=40)


def test_single_list_report_rejects_a_negative_cap() -> None:
    with pytest.raises(ValueError, match="cap must be non-negative"):
        project_single_list_report({"findings": ROWS}, "findings", cap=-1)
