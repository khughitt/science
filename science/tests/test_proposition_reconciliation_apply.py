import pytest

from science_tool.annotation.proposition_reconciliation import judgment_id
from science_tool.annotation.proposition_reconciliation_plan import (
    ReconciliationAction,
    ReconciliationActionPlan,
    reconciliation_action_id,
)
from science_tool.annotation.proposition_reconciliation_apply import (
    ReconciliationApplyError,
    select_canonicalization_actions,
)


def _action(
    *,
    kind: str = "canonicalize_propositions",
    status: str = "ready",
    action_id: str | None = None,
    canonical: str | None = "proposition:a",
    members: tuple[str, ...] = ("proposition:a", "proposition:b"),
    blockers: tuple[dict, ...] = (),
) -> ReconciliationAction:
    judgment = judgment_id("same_claim", "same_claim", members)
    return ReconciliationAction(
        action_id=action_id
        or reconciliation_action_id(kind, judgment, canonical or members[0], members[1:]),
        kind=kind,
        status=status,
        decision="same_claim",
        candidate_id="reconcile:same-claim/candidate",
        judgment_id=judgment,
        confidence="high",
        rationale="Same claim.",
        source_review="review.json",
        review_source="llm-review:claude:proposition-reconcile-v1",
        canonical_proposition=canonical,
        members=members,
        inputs={
            "source_ref_moves": (
                {"from": "proposition:b", "to": "proposition:a", "source_refs": ("paper:B",)},
            ),
            "sidecar_backlink_rewrites": (
                {
                    "from": "proposition:b",
                    "to": "proposition:a",
                    "annotation_refs": ("annotation:entities/papers/B.source#b1",),
                },
            ),
            "archive_candidates": ("proposition:b",),
        },
        blockers=blockers,
    )


def test_select_canonicalization_actions_returns_all_ready_when_unfiltered():
    ready = _action()
    advisory = _action(kind="record_reconciliation_decision", status="advisory", canonical=None)
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(advisory, ready)
    )

    selected = select_canonicalization_actions(plan, requested_action_ids=())

    assert selected == (ready,)


def test_select_canonicalization_actions_rejects_plan_errors():
    plan = ReconciliationActionPlan(
        schema_version=1,
        source_reviews=("review.json",),
        actions=(_action(),),
        errors=({"reason": "component-too-large", "detail": "too many", "members": []},),
    )

    with pytest.raises(ReconciliationApplyError, match="action plan has top-level errors"):
        select_canonicalization_actions(plan, requested_action_ids=())


def test_select_canonicalization_actions_rejects_requested_advisory_action():
    advisory = _action(
        kind="record_reconciliation_decision",
        status="advisory",
        canonical=None,
        action_id="reconcile-action:advisory",
    )
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(advisory,)
    )

    with pytest.raises(ReconciliationApplyError, match="not executable by Half C"):
        select_canonicalization_actions(plan, requested_action_ids=("reconcile-action:advisory",))


def test_select_canonicalization_actions_rejects_empty_applicable_set():
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=("review.json",), actions=())

    with pytest.raises(ReconciliationApplyError, match="no ready canonicalize_propositions actions"):
        select_canonicalization_actions(plan, requested_action_ids=())
