import hashlib

from science_tool.annotation.proposition_reconciliation import (
    FactorizationCandidate,
    PropositionSnapshot,
    ReconciliationFault,
    ReconciliationReport,
    candidate_id,
    judgment_id,
)
from science_tool.annotation.proposition_reconciliation_plan import (
    ReviewedReconciliationInput,
    action_plan_to_json,
    build_reconciliation_action_plan,
    reconciliation_action_id,
)


def _snapshot(ref: str) -> PropositionSnapshot:
    return PropositionSnapshot(
        ref=ref,
        title=ref,
        source_refs=frozenset({"paper:A2020", "annotation:entities/papers/A2020.source#a1"}),
        paper_refs=frozenset({"paper:A2020"}),
        annotation_refs=frozenset({"annotation:entities/papers/A2020.source#a1"}),
    )


def _factor_candidate(
    *,
    proposition: str = "proposition:p",
    candidate_ref: str | None = None,
    recommended_action: str = "factorization_needs_resynthesis",
) -> FactorizationCandidate:
    return FactorizationCandidate(
        candidate_id=candidate_ref or candidate_id("factorization_disagreement", [proposition]),
        proposition=proposition,
        priority="high",
        papers=("paper:A2020", "paper:B2021"),
        current={
            "subject": None,
            "predicate": None,
            "object": None,
            "polarity": None,
            "claim_layer": None,
        },
        observed_statement_hints=(
            {
                "paper": "paper:A2020",
                "annotation": "annotation:entities/papers/A2020.source#a1",
                "stance": "asserted",
                "section": "results",
                "subject": None,
                "object": None,
                "subject_concept": None,
                "object_concept": None,
                "exact": "BES behaves similarly to meta-analysis in many settings.",
            },
            {
                "paper": "paper:B2021",
                "annotation": "annotation:entities/papers/B2021.source#b1",
                "stance": "negated",
                "section": "results",
                "subject": None,
                "object": None,
                "subject_concept": None,
                "object_concept": None,
                "exact": "BES does not behave like data pooling.",
            },
        ),
        disagreement=("stance mix requires review",),
        recommended_action=recommended_action,
    )


def _factor_review(
    candidate: FactorizationCandidate,
    *,
    decision: str = "factorization_needs_resynthesis",
) -> dict:
    return {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "factorization_disagreement", decision, [candidate.proposition]
                ),
                "lane": "factorization_disagreement",
                "decision": decision,
                "proposition": candidate.proposition,
                "rationale": "This broad proposition bundles distinct claim families.",
                "confidence": "high",
            }
        ],
    }


def test_reconciliation_action_id_uses_full_sha256_of_action_and_refs():
    expected = hashlib.sha256(
        b"resynthesize_proposition\x00reconcile:judgment:j1\x00proposition:p"
    ).hexdigest()

    assert reconciliation_action_id(
        "resynthesize_proposition",
        "reconcile:judgment:j1",
        "proposition:p",
    ) == f"reconcile-action:{expected}"


def test_factorization_resynthesis_review_maps_to_ready_action():
    candidate = _factor_candidate()
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={candidate.proposition: _snapshot(candidate.proposition)},
    )
    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/factorization.json",
                doc=_factor_review(candidate),
            )
        ],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "resynthesize_proposition"
    assert action.status == "ready"
    assert action.proposition == "proposition:p"
    assert action.decision == "factorization_needs_resynthesis"
    assert action.blockers == ()
    assert action.writes == ()
    assert action.inputs["annotations"] == (
        "annotation:entities/papers/A2020.source#a1",
        "annotation:entities/papers/B2021.source#b1",
    )
    assert action.inputs["papers"] == ("paper:A2020", "paper:B2021")
    assert action.suggested_operations[0]["kind"] == "draft_proposition"


def test_report_faults_become_top_level_action_plan_errors():
    report = ReconciliationReport(
        faults=(
            ReconciliationFault(
                reason="missing-proposition",
                detail="proposition:p has no snapshot",
            ),
        )
    )
    payload = action_plan_to_json(build_reconciliation_action_plan(report, []))

    assert payload["summary"]["errors"] == 1
    assert payload["errors"] == [
        {
            "reason": "missing-proposition",
            "detail": "proposition:p has no snapshot",
            "members": [],
        }
    ]
