"""Deterministic lifecycle adjudication (design §2)."""

from __future__ import annotations

from science_tool.correspondence.adjudicate import Adjudicated, adjudicate
from science_tool.correspondence.probe import ProbeResult, TaskState

P, A, U = ProbeResult.PRESENT, ProbeResult.ABSENT, ProbeResult.UNKNOWN


# --- adjudication (design §6.2) ---

def test_all_present_and_tasks_done_is_complete():
    assert adjudicate([P, P], [TaskState.DONE], superseded=False) is Adjudicated.COMPLETE


def test_all_present_and_no_tasks_referenced_is_complete():
    """Task linkage is ~48% at best -- absence of a task ref must not block `complete`."""
    assert adjudicate([P, P], [], superseded=False) is Adjudicated.COMPLETE


def test_all_present_but_task_active_is_active():
    assert adjudicate([P, P], [TaskState.ACTIVE], superseded=False) is Adjudicated.ACTIVE


def test_partial_deliverables_is_active():
    assert adjudicate([P, A], [], superseded=False) is Adjudicated.ACTIVE


def test_nothing_present_and_no_tasks_started_is_draft():
    assert adjudicate([A, A], [], superseded=False) is Adjudicated.DRAFT


def test_any_unknown_probe_is_indeterminate():
    assert adjudicate([P, U], [], superseded=False) is Adjudicated.INDETERMINATE


def test_no_deliverables_extracted_is_indeterminate():
    """Nothing was probed, so nothing was established."""
    assert adjudicate([], [], superseded=False) is Adjudicated.INDETERMINATE


def test_superseded_dominates():
    assert adjudicate([A, A], [], superseded=True) is Adjudicated.SUPERSEDED


# --- fb-2026-07-26-013: a task ref the instrument could not place is not evidence ---

def test_unresolvable_task_ref_is_indeterminate():
    """MISSING used to feed `tasks_unstarted`, so a plan whose tasks were all
    done-and-archived read as unstarted and could adjudicate DRAFT."""
    assert adjudicate([P, P], [TaskState.MISSING], superseded=False) is Adjudicated.INDETERMINATE


def test_retired_task_ref_is_indeterminate():
    assert adjudicate([P, P], [TaskState.UNKNOWN], superseded=False) is Adjudicated.INDETERMINATE


def test_one_unresolvable_ref_poisons_an_otherwise_complete_plan():
    assert (
        adjudicate([P, P], [TaskState.DONE, TaskState.MISSING], superseded=False)
        is Adjudicated.INDETERMINATE
    )


def test_nothing_present_with_a_resolvable_active_task_is_active_not_draft():
    """A cited task that is genuinely in flight is evidence the plan has started."""
    assert adjudicate([A, A], [TaskState.ACTIVE], superseded=False) is Adjudicated.ACTIVE
