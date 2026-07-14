"""The consumers that read the hypothesis vocabulary — after the fold.

Every consumer that asked "is this hypothesis still live?" was reading a `status` field that held
the epistemic VERDICT. The verdict moved to `verdict` and the lifecycle moved into `status`, so each
of these had to be re-pointed. The tests that matter here are the ones that pin what did NOT move:
the QUESTION vocabulary, which still encodes answeredness in `status` because the question slice has
not run. A consumer rewritten across kind boundaries would silently reopen every answered question
in the corpus.
"""

from __future__ import annotations

from science_tool.graph.attention import DEBT_QUESTION_STATUSES
from science_tool.validate.checks.dataset_capabilities import is_demand_closed


def test_demand_closed_reads_the_hypothesis_VERDICT_now() -> None:
    # `refuted` was the ONLY hypothesis-specific value any consumer read. It is a verdict now.
    assert is_demand_closed(kind="hypothesis", status="active", verdict="refuted") is True
    assert is_demand_closed(kind="hypothesis", status="active", verdict="supported") is False
    assert is_demand_closed(kind="hypothesis", status="retired", verdict=None) is True


def test_a_REFUTED_hypothesis_that_is_still_being_WORKED_is_not_closed_by_its_LIFECYCLE() -> None:
    # The two axes, and the cell that proves they are two. `refuted` + `active` is a real state --
    # disproved, still being written up. It is demand-CLOSED (the claim needs no more data) and
    # lifecycle-OPEN (somebody is still working on it), and no single field could say both.
    assert is_demand_closed(kind="hypothesis", status="active", verdict="refuted") is True
    from science_tool.entities import CLOSED_LIFECYCLE_STATUSES

    assert "active" not in CLOSED_LIFECYCLE_STATUSES
    assert "refuted" not in CLOSED_LIFECYCLE_STATUSES  # a VERDICT is never a lifecycle state


def test_QUESTION_demand_closure_is_UNCHANGED() -> None:
    # The question slice has not happened. Its statuses still carry answeredness, and this predicate
    # must keep reading them exactly as it does today.
    assert is_demand_closed(kind="question", status="answered", verdict=None) is True
    assert is_demand_closed(kind="question", status="active", verdict=None) is False
    # ...and the residual-demand states stay LIVE, as they were.
    assert is_demand_closed(kind="question", status="partially-answered", verdict=None) is False
    assert is_demand_closed(kind="question", status="deferred", verdict=None) is False


def test_a_question_is_not_read_through_the_HYPOTHESIS_rules() -> None:
    # The failure mode the kind split exists to prevent. `answered` is not a lifecycle word and it is
    # not a verdict -- if the hypothesis branch were applied to a question, an answered question
    # would come back LIVE and every one in the corpus would silently reopen.
    assert is_demand_closed(kind="question", status="answered", verdict=None) is True
    assert is_demand_closed(kind="hypothesis", status="answered", verdict=None) is False


def test_question_debt_is_untouched() -> None:
    assert DEBT_QUESTION_STATUSES == frozenset({"active", "partially-answered", "deferred"})
