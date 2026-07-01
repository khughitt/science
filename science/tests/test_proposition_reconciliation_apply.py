import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation import io as anno_io
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.proposition_reconciliation import judgment_id
from science_tool.annotation.proposition_reconciliation_plan import (
    ReconciliationAction,
    ReconciliationActionPlan,
    ReviewedReconciliationInput,
    build_reconciliation_action_plan,
    reconciliation_action_id,
)
from science_tool.annotation.proposition_reconciliation_apply import (
    ReconciliationApplyError,
    plan_canonicalization_apply,
    select_canonicalization_actions,
)

_CREATED = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _action(
    *,
    kind: str = "canonicalize_propositions",
    status: str = "ready",
    action_id: str | None = None,
    canonical: str | None = "proposition:a",
    members: tuple[str, ...] = ("proposition:a", "proposition:b"),
    blockers: tuple[dict, ...] = (),
    inputs: dict | None = None,
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
        inputs=inputs or {
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


def _manifest(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _proposition(
    root: Path,
    slug: str,
    title: str,
    *,
    source_refs: tuple[str, ...] = (),
    status: str = "active",
    superseded_by: str | None = None,
    subject: str = "BRCA1 loss",
    object_: str = "genomic instability",
) -> None:
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    refs = "".join(f"  - {ref}\n" for ref in source_refs)
    superseded = f"superseded_by: {superseded_by}\n" if superseded_by else ""
    path.write_text(
        "---\n"
        f"id: proposition:{slug}\n"
        "type: proposition\n"
        f"title: {title}\n"
        f"status: {status}\n"
        f"{superseded}"
        f"subject: {subject}\n"
        "predicate: increases\n"
        f"object: {object_}\n"
        "polarity: positive\n"
        "source_refs:\n"
        f"{refs}"
        "---\n\n"
        "Claim.\n",
        encoding="utf-8",
    )


def _ann(annotation_id: str, promoted_to: str) -> Annotation:
    body = json.dumps({"section": "results", "stance": "asserted"})
    return Annotation(
        id=annotation_id,
        target=SpecificResource(
            source="x.source.md",
            selector=TextQuoteSelector(exact=annotation_id, prefix="", suffix=""),
        ),
        bodies=(TextualBody(value=body, format="application/json"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1",
        status=Status.OPEN,
        creator="paper-annotate",
        created=_CREATED,
        content_hash="0" * 64,
        promoted_to=promoted_to,
    )


def _paper_sidecar(root: Path, citekey: str, annotations: tuple[Annotation, ...]) -> Path:
    md = root / "entities" / "papers" / f"{citekey}.source.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("Results show the claim.\n", encoding="utf-8")
    sidecar_path = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sidecar_path, Sidecar(annotations=annotations))
    return sidecar_path


def _review_doc_for_current_candidate(
    root: Path,
    canonical: str = "proposition:a",
) -> dict:
    from science_tool.annotation.proposition_reconciliation import build_reconciliation_report

    report = build_reconciliation_report(root)
    candidate = report.same_claim_candidates[0]
    members = list(candidate.propositions)
    return {
        "report": report,
        "review": {
            "source": "llm-review:claude:proposition-reconcile-v1",
            "judgments": [
                {
                    "candidate_id": candidate.candidate_id,
                    "judgment_id": judgment_id("same_claim", "same_claim", members),
                    "lane": "same_claim",
                    "decision": "same_claim",
                    "canonical_proposition": canonical,
                    "members": members,
                    "rationale": "The propositions express the same claim.",
                    "confidence": "high",
                }
            ],
        },
    }


def _ready_plan(root: Path, review_doc: dict) -> ReconciliationActionPlan:
    return build_reconciliation_action_plan(
        review_doc["report"],
        [
            ReviewedReconciliationInput(
                path=str(root / "reviews" / "same-claim.json"),
                doc=review_doc["review"],
            )
        ],
    )


def _manual_ready_plan(
    actions: tuple[ReconciliationAction, ...] | None = None,
) -> ReconciliationActionPlan:
    return ReconciliationActionPlan(
        schema_version=1,
        source_reviews=("review.json",),
        actions=actions or (_action(),),
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


def test_plan_canonicalization_apply_uses_live_sidecar_backlinks_not_only_half_b_inputs(
    tmp_path: Path,
):
    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/A2020.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021",),
    )
    _paper_sidecar(tmp_path, "B2021", (_ann("b1", "proposition:b"),))
    action = _action(
        inputs={
            "source_ref_moves": (
                {"from": "proposition:b", "to": "proposition:a", "source_refs": ("paper:B2021",)},
            ),
            "sidecar_backlink_rewrites": (
                {
                    "from": "proposition:b",
                    "to": "proposition:a",
                    "annotation_refs": (),
                },
            ),
            "archive_candidates": ("proposition:b",),
        }
    )

    preflight = plan_canonicalization_apply(tmp_path, _manual_ready_plan((action,)))

    canonical_edit = next(edit for edit in preflight.file_edits if edit.path.name == "a.md")
    assert "paper:B2021" in canonical_edit.final_text
    assert "annotation:entities/papers/B2021.source#b1" in canonical_edit.final_text
    assert preflight.expected_source_refs_by_canonical == {
        "proposition:a": (
            "annotation:entities/papers/B2021.source#b1",
            "paper:B2021",
        )
    }
    assert any(
        diagnostic.get("reason") == "half_b_missing_live_backlink"
        for diagnostic in preflight.diagnostics
    )


def test_plan_canonicalization_apply_merges_distinct_rewrites_in_same_sidecar(
    tmp_path: Path,
):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")
    _proposition(
        tmp_path,
        "c",
        "TP53 loss increases genomic instability",
        subject="TP53 loss",
    )
    _proposition(
        tmp_path,
        "d",
        "Loss of TP53 raises genome instability",
        subject="TP53 loss",
    )
    _paper_sidecar(
        tmp_path,
        "Shared",
        (
            _ann("b1", "proposition:b"),
            _ann("d1", "proposition:d"),
        ),
    )
    first = _action(
        action_id="reconcile-action:first",
        canonical="proposition:a",
        members=("proposition:a", "proposition:b"),
        inputs={
            "source_ref_moves": (),
            "sidecar_backlink_rewrites": (
                {
                    "from": "proposition:b",
                    "to": "proposition:a",
                    "annotation_refs": ("annotation:entities/papers/Shared.source#b1",),
                },
            ),
            "archive_candidates": ("proposition:b",),
        },
    )
    second = _action(
        action_id="reconcile-action:second",
        canonical="proposition:c",
        members=("proposition:c", "proposition:d"),
        inputs={
            "source_ref_moves": (),
            "sidecar_backlink_rewrites": (
                {
                    "from": "proposition:d",
                    "to": "proposition:c",
                    "annotation_refs": ("annotation:entities/papers/Shared.source#d1",),
                },
            ),
            "archive_candidates": ("proposition:d",),
        },
    )

    preflight = plan_canonicalization_apply(tmp_path, _manual_ready_plan((first, second)))

    sidecar_edits = [
        edit for edit in preflight.file_edits if edit.path.name == "Shared.source.anno.trig"
    ]
    assert len(sidecar_edits) == 1
    assert "proposition:a" in sidecar_edits[0].final_text
    assert "proposition:c" in sidecar_edits[0].final_text
    assert "proposition:b" not in sidecar_edits[0].final_text
    assert "proposition:d" not in sidecar_edits[0].final_text


def test_plan_canonicalization_apply_errors_when_duplicate_superseded_elsewhere(
    tmp_path: Path,
):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        status="superseded",
        superseded_by="proposition:other",
    )
    _paper_sidecar(tmp_path, "B", (_ann("b1", "proposition:b"),))

    with pytest.raises(
        ReconciliationApplyError,
        match="superseded_by proposition:other",
    ):
        plan_canonicalization_apply(tmp_path, _manual_ready_plan())
