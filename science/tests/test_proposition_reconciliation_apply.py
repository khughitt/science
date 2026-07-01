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


def test_select_canonicalization_actions_ignores_unrequested_non_ready_and_blocked_actions():
    blocked = _action(
        action_id="reconcile-action:blocked",
        blockers=({"reason": "manual-review-required", "detail": "conflicting source refs"},),
    )
    non_ready = _action(status="blocked", action_id="reconcile-action:not-ready")
    ready = _action(
        action_id="reconcile-action:ready",
        canonical="proposition:c",
        members=("proposition:c", "proposition:d"),
    )
    plan = ReconciliationActionPlan(
        schema_version=1,
        source_reviews=("review.json",),
        actions=(blocked, non_ready, ready),
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


def test_select_canonicalization_actions_includes_plan_error_reason_and_detail():
    plan = ReconciliationActionPlan(
        schema_version=1,
        source_reviews=("review.json",),
        actions=(_action(),),
        errors=({"reason": "component-too-large", "detail": "too many", "members": []},),
    )

    with pytest.raises(ReconciliationApplyError) as exc_info:
        select_canonicalization_actions(plan, requested_action_ids=())

    message = str(exc_info.value)
    assert "action plan has top-level errors" in message
    assert "component-too-large" in message
    assert "too many" in message


def test_select_canonicalization_actions_rejects_malformed_top_level_error_type():
    plan = ReconciliationActionPlan(
        schema_version=1,
        source_reviews=("review.json",),
        actions=(_action(),),
        errors=("bad",),
    )

    with pytest.raises(
        ReconciliationApplyError,
        match="action plan has malformed top-level error at index 0",
    ):
        select_canonicalization_actions(plan, requested_action_ids=())


def test_select_canonicalization_actions_rejects_requested_resynthesis_action():
    action = _action(
        kind="resynthesize_proposition",
        action_id="reconcile-action:resynthesize",
        canonical="proposition:a",
    )
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(action,)
    )

    with pytest.raises(
        ReconciliationApplyError,
        match="resynthesize_proposition; factorization resynthesis is not executable",
    ):
        select_canonicalization_actions(
            plan, requested_action_ids=("reconcile-action:resynthesize",)
        )


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


def test_select_canonicalization_actions_rejects_unknown_requested_ids():
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(_action(),)
    )

    with pytest.raises(
        ReconciliationApplyError, match="unknown reconciliation action\\(s\\): reconcile-action:missing"
    ):
        select_canonicalization_actions(plan, requested_action_ids=("reconcile-action:missing",))


def test_select_canonicalization_actions_rejects_duplicate_requested_ids():
    action = _action(action_id="reconcile-action:deduplicate")
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(action,)
    )

    with pytest.raises(
        ReconciliationApplyError, match="duplicate reconciliation action request\\(s\\):"
    ):
        select_canonicalization_actions(
            plan,
            requested_action_ids=(
                "reconcile-action:deduplicate",
                "reconcile-action:deduplicate",
            ),
        )


def test_select_canonicalization_actions_rejects_duplicate_plan_action_ids_requested_mode():
    first = _action(action_id="reconcile-action:duplicate")
    second = _action(
        action_id="reconcile-action:duplicate",
        canonical="proposition:c",
        members=("proposition:c", "proposition:d"),
    )
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(first, second)
    )

    with pytest.raises(
        ReconciliationApplyError,
        match="duplicate reconciliation action id\\(s\\) in plan: reconcile-action:duplicate",
    ):
        select_canonicalization_actions(
            plan, requested_action_ids=("reconcile-action:duplicate",)
        )


def test_select_canonicalization_actions_rejects_duplicate_plan_action_ids_unrequested_mode():
    first = _action(action_id="reconcile-action:duplicate")
    second = _action(
        action_id="reconcile-action:duplicate",
        canonical="proposition:c",
        members=("proposition:c", "proposition:d"),
    )
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(first, second)
    )

    with pytest.raises(
        ReconciliationApplyError,
        match="duplicate reconciliation action id\\(s\\) in plan: reconcile-action:duplicate",
    ):
        select_canonicalization_actions(plan, requested_action_ids=())


def test_select_canonicalization_actions_rejects_requested_non_ready_action():
    action = _action(status="blocked", action_id="reconcile-action:not-ready")
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(action,)
    )

    with pytest.raises(ReconciliationApplyError, match="reconcile-action:not-ready is blocked"):
        select_canonicalization_actions(
            plan, requested_action_ids=("reconcile-action:not-ready",)
        )


def test_select_canonicalization_actions_rejects_requested_action_with_blockers():
    action = _action(
        action_id="reconcile-action:blocked",
        blockers=({"reason": "manual-review-required", "detail": "conflicting source refs"},),
    )
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(action,)
    )

    with pytest.raises(ReconciliationApplyError) as exc_info:
        select_canonicalization_actions(plan, requested_action_ids=("reconcile-action:blocked",))

    message = str(exc_info.value)
    assert "reconcile-action:blocked has blocker(s)" in message
    assert "manual-review-required" in message
    assert "conflicting source refs" in message


def test_select_canonicalization_actions_rejects_malformed_action_blocker():
    action = _action(
        action_id="reconcile-action:blocked",
        blockers=({"detail": "missing reason"},),
    )
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(action,)
    )

    with pytest.raises(
        ReconciliationApplyError,
        match="reconcile-action:blocked has malformed blocker at index 0",
    ):
        select_canonicalization_actions(plan, requested_action_ids=("reconcile-action:blocked",))


def test_select_canonicalization_actions_rejects_malformed_action_blocker_type():
    action = _action(
        action_id="reconcile-action:blocked",
        blockers=("bad",),
    )
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(action,)
    )

    with pytest.raises(
        ReconciliationApplyError,
        match="reconcile-action:blocked has malformed blocker at index 0",
    ):
        select_canonicalization_actions(plan, requested_action_ids=("reconcile-action:blocked",))


def test_select_canonicalization_actions_rejects_missing_canonical_proposition():
    action = _action(canonical=None, action_id="reconcile-action:no-canonical")
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(action,)
    )

    with pytest.raises(ReconciliationApplyError, match="has no canonical_proposition"):
        select_canonicalization_actions(
            plan, requested_action_ids=("reconcile-action:no-canonical",)
        )


def test_select_canonicalization_actions_rejects_too_few_members():
    action = _action(
        action_id="reconcile-action:one-member",
        canonical="proposition:a",
        members=("proposition:a",),
    )
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(action,)
    )

    with pytest.raises(ReconciliationApplyError, match="has fewer than two members"):
        select_canonicalization_actions(
            plan, requested_action_ids=("reconcile-action:one-member",)
        )


def test_select_canonicalization_actions_rejects_overlapping_selected_members():
    first = _action(
        action_id="reconcile-action:first",
        canonical="proposition:a",
        members=("proposition:a", "proposition:b"),
    )
    second = _action(
        action_id="reconcile-action:second",
        canonical="proposition:c",
        members=("proposition:b", "proposition:c"),
    )
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(first, second)
    )

    with pytest.raises(ReconciliationApplyError, match="targeted by multiple selected actions"):
        select_canonicalization_actions(plan, requested_action_ids=())


def test_select_canonicalization_actions_sorts_requested_mode_by_action_id():
    beta = _action(action_id="reconcile-action:beta")
    alpha = _action(
        action_id="reconcile-action:alpha",
        canonical="proposition:c",
        members=("proposition:c", "proposition:d"),
    )
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(beta, alpha)
    )

    selected = select_canonicalization_actions(
        plan,
        requested_action_ids=("reconcile-action:beta", "reconcile-action:alpha"),
    )

    assert tuple(action.action_id for action in selected) == (
        "reconcile-action:alpha",
        "reconcile-action:beta",
    )


def test_select_canonicalization_actions_sorts_unrequested_mode_by_action_id():
    beta = _action(action_id="reconcile-action:beta")
    alpha = _action(
        action_id="reconcile-action:alpha",
        canonical="proposition:c",
        members=("proposition:c", "proposition:d"),
    )
    plan = ReconciliationActionPlan(
        schema_version=1, source_reviews=("review.json",), actions=(beta, alpha)
    )

    selected = select_canonicalization_actions(plan, requested_action_ids=())

    assert tuple(action.action_id for action in selected) == (
        "reconcile-action:alpha",
        "reconcile-action:beta",
    )


def test_select_canonicalization_actions_rejects_empty_applicable_set():
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=("review.json",), actions=())

    with pytest.raises(ReconciliationApplyError, match="no ready canonicalize_propositions actions"):
        select_canonicalization_actions(plan, requested_action_ids=())
