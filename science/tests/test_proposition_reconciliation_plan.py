import hashlib

from science_tool.annotation.proposition_reconciliation import (
    FactorizationCandidate,
    PropositionSnapshot,
    ReconciliationFault,
    ReconciliationReport,
    build_same_claim_candidates,
    candidate_id,
    factorization_assertion_fingerprint,
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


def _same_claim_snapshot(
    ref: str,
    title: str,
    *,
    paper: str,
    annotation: str,
) -> PropositionSnapshot:
    return PropositionSnapshot(
        ref=ref,
        title=title,
        subject="BRCA1 loss",
        predicate="increases",
        object="genomic instability",
        polarity="positive",
        source_refs=frozenset({paper, annotation}),
        paper_refs=frozenset({paper}),
        annotation_refs=frozenset({annotation}),
    )


def _same_claim_report() -> ReconciliationReport:
    snapshots = {
        "proposition:a": _same_claim_snapshot(
            "proposition:a",
            "BRCA1 loss increases genomic instability",
            paper="paper:A2020",
            annotation="annotation:entities/papers/A2020.source#a1",
        ),
        "proposition:b": _same_claim_snapshot(
            "proposition:b",
            "Loss of BRCA1 raises genome instability",
            paper="paper:B2021",
            annotation="annotation:entities/papers/B2021.source#b1",
        ),
    }
    same = build_same_claim_candidates(list(snapshots.values()))
    return ReconciliationReport(
        same_claim_candidates=same.candidates,
        faults=same.faults,
        proposition_snapshots=snapshots,
    )


def _same_claim_review(report: ReconciliationReport) -> dict:
    candidate = report.same_claim_candidates[0]
    members = list(candidate.propositions)
    return {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id("same_claim", "same_claim", members),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": members,
                "rationale": "The propositions express the same claim.",
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


def test_factorization_resynthesis_action_plan_json_uses_list_shapes():
    candidate = _factor_candidate()
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={candidate.proposition: _snapshot(candidate.proposition)},
    )
    payload = action_plan_to_json(
        build_reconciliation_action_plan(
            report,
            [
                ReviewedReconciliationInput(
                    path="reviews/factorization.json",
                    doc=_factor_review(candidate),
                )
            ],
        )
    )

    action = payload["actions"][0]
    assert action["proposition"] == "proposition:p"
    assert action["writes"] == []
    assert action["inputs"]["annotations"] == [
        "annotation:entities/papers/A2020.source#a1",
        "annotation:entities/papers/B2021.source#b1",
    ]
    assert isinstance(action["inputs"]["annotations"], list)
    assert isinstance(action["inputs"]["papers"], list)
    assert action["suggested_operations"][0]["kind"] == "draft_proposition"


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


def test_same_claim_review_maps_to_canonicalization_action():
    report = _same_claim_report()
    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/same-claim.json",
                doc=_same_claim_review(report),
            )
        ],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "canonicalize_propositions"
    assert action.status == "ready"
    assert action.canonical_proposition == "proposition:a"
    assert action.members == ("proposition:a", "proposition:b")
    assert action.inputs["source_ref_moves"] == (
        {
            "from": "proposition:b",
            "to": "proposition:a",
            "source_refs": (
                "annotation:entities/papers/B2021.source#b1",
                "paper:B2021",
            ),
        },
    )
    assert action.inputs["sidecar_backlink_rewrites"] == (
        {
            "from": "proposition:b",
            "to": "proposition:a",
            "annotation_refs": ("annotation:entities/papers/B2021.source#b1",),
        },
    )
    assert action.writes == ()


def test_same_claim_review_with_padded_lane_maps_to_canonicalization_action():
    report = _same_claim_report()
    review = _same_claim_review(report)
    review["judgments"][0]["lane"] = "  same_claim  "

    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/same-claim.json",
                doc=review,
            )
        ],
    )

    assert len(plan.actions) == 1
    assert plan.actions[0].kind == "canonicalize_propositions"


def test_same_claim_review_with_padded_canonical_proposition_plans_stripped_ref():
    report = _same_claim_report()
    review = _same_claim_review(report)
    review["judgments"][0]["canonical_proposition"] = " proposition:a "

    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/same-claim.json",
                doc=review,
            )
        ],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.canonical_proposition == "proposition:a"
    assert action.members == ("proposition:a", "proposition:b")
    assert action.inputs["source_ref_moves"] == (
        {
            "from": "proposition:b",
            "to": "proposition:a",
            "source_refs": (
                "annotation:entities/papers/B2021.source#b1",
                "paper:B2021",
            ),
        },
    )
    assert action.inputs["archive_candidates"] == ("proposition:b",)


def test_same_claim_needs_human_maps_to_blocked_human_review_action():
    report = _same_claim_report()
    candidate = report.same_claim_candidates[0]
    members = list(candidate.propositions)
    rationale = "The candidate needs reviewer judgment before planning writes."
    review = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id("same_claim", "needs_human", members),
                "lane": "same_claim",
                "decision": "needs_human",
                "members": members,
                "rationale": rationale,
                "confidence": "medium",
            }
        ],
    }

    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/same-claim.json",
                doc=review,
            )
        ],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "needs_human_review"
    assert action.status == "blocked"
    assert action.decision == "needs_human"
    assert action.blockers == ({"reason": "needs_human", "detail": rationale},)
    assert action.writes == ()


def test_same_claim_needs_human_with_padded_decision_maps_to_blocked_action():
    report = _same_claim_report()
    candidate = report.same_claim_candidates[0]
    members = list(candidate.propositions)
    rationale = "The candidate needs reviewer judgment before planning writes."
    review = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id("same_claim", "needs_human", members),
                "lane": "same_claim",
                "decision": " needs_human ",
                "members": members,
                "rationale": rationale,
                "confidence": "medium",
            }
        ],
    }

    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/same-claim.json",
                doc=review,
            )
        ],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "needs_human_review"
    assert action.status == "blocked"
    assert action.decision == "needs_human"
    assert action.blockers == ({"reason": "needs_human", "detail": rationale},)


def test_review_incomplete_blocks_same_claim_canonicalization():
    snapshots = {
        "proposition:a": _same_claim_snapshot(
            "proposition:a",
            "BRCA1 loss increases genomic instability",
            paper="paper:A2020",
            annotation="annotation:entities/papers/A2020.source#a1",
        ),
        "proposition:b": _same_claim_snapshot(
            "proposition:b",
            "Loss of BRCA1 raises genome instability",
            paper="paper:B2021",
            annotation="annotation:entities/papers/B2021.source#b1",
        ),
        "proposition:c": _same_claim_snapshot(
            "proposition:c",
            "BRCA1 loss promotes genomic instability",
            paper="paper:C2022",
            annotation="annotation:entities/papers/C2022.source#c1",
        ),
    }
    same = build_same_claim_candidates(list(snapshots.values()))
    report = ReconciliationReport(
        same_claim_candidates=same.candidates,
        faults=same.faults,
        proposition_snapshots=snapshots,
    )
    review = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate_id(
                    "same_claim", ["proposition:a", "proposition:b"]
                ),
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", ["proposition:a", "proposition:b"]
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": ["proposition:a", "proposition:b"],
                "rationale": "The reviewed pair expresses the same claim.",
                "confidence": "high",
            }
        ],
    }

    plan = build_reconciliation_action_plan(
        report,
        [ReviewedReconciliationInput(path="reviews/same-claim.json", doc=review)],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "canonicalize_propositions"
    assert action.status == "blocked"
    assert action.blockers == (
        {
            "reason": "review_incomplete",
            "detail": "candidate has unreviewed members: proposition:c",
        },
    )
    assert action.inputs["archive_candidates"] == ("proposition:b",)


def test_splittable_subset_canonicalization_inputs_exclude_non_members():
    snapshots = {
        "proposition:a": _same_claim_snapshot(
            "proposition:a",
            "BRCA1 loss increases genomic instability",
            paper="paper:A2020",
            annotation="annotation:entities/papers/A2020.source#a1",
        ),
        "proposition:b": _same_claim_snapshot(
            "proposition:b",
            "Loss of BRCA1 raises genome instability",
            paper="paper:B2021",
            annotation="annotation:entities/papers/B2021.source#b1",
        ),
        "proposition:c": _same_claim_snapshot(
            "proposition:c",
            "BRCA1 loss promotes genomic instability",
            paper="paper:C2022",
            annotation="annotation:entities/papers/C2022.source#c1",
        ),
    }
    same = build_same_claim_candidates(list(snapshots.values()))
    report = ReconciliationReport(
        same_claim_candidates=same.candidates,
        faults=same.faults,
        proposition_snapshots=snapshots,
    )
    candidate = report.same_claim_candidates[0]
    review = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", ["proposition:a", "proposition:b"]
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": ["proposition:a", "proposition:b"],
                "rationale": "The reviewed pair expresses the same claim.",
                "confidence": "high",
            },
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "same_claim", "related_but_distinct", ["proposition:c"]
                ),
                "lane": "same_claim",
                "decision": "related_but_distinct",
                "members": ["proposition:c"],
                "rationale": "This member should not be merged with the pair.",
                "confidence": "high",
            },
        ],
    }

    plan = build_reconciliation_action_plan(
        report,
        [ReviewedReconciliationInput(path="reviews/same-claim.json", doc=review)],
    )

    canonical_action = next(
        action for action in plan.actions if action.kind == "canonicalize_propositions"
    )
    assert canonical_action.status == "ready"
    assert canonical_action.inputs["source_ref_moves"] == (
        {
            "from": "proposition:b",
            "to": "proposition:a",
            "source_refs": (
                "annotation:entities/papers/B2021.source#b1",
                "paper:B2021",
            ),
        },
    )
    assert canonical_action.inputs["archive_candidates"] == ("proposition:b",)


def test_stance_review_needed_maps_to_blocked_stance_review_action():
    candidate = _factor_candidate(recommended_action="stance_review_needed")
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={candidate.proposition: _snapshot(candidate.proposition)},
    )
    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/factorization.json",
                doc=_factor_review(candidate, decision="stance_review_needed"),
            )
        ],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "review_annotation_stance"
    assert action.status == "blocked"
    assert action.blockers == (
        {
            "reason": "stance_review_needed",
            "detail": "This broad proposition bundles distinct claim families.",
        },
    )


def test_factorization_with_padded_decision_maps_to_stripped_kind_and_status():
    candidate = _factor_candidate(recommended_action="stance_review_needed")
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={candidate.proposition: _snapshot(candidate.proposition)},
    )
    review = _factor_review(candidate, decision="stance_review_needed")
    review["judgments"][0]["decision"] = " stance_review_needed "

    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/factorization.json",
                doc=review,
            )
        ],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "review_annotation_stance"
    assert action.status == "blocked"
    assert action.decision == "stance_review_needed"
    assert action.blockers == (
        {
            "reason": "stance_review_needed",
            "detail": "This broad proposition bundles distinct claim families.",
        },
    )


def test_insufficient_hints_maps_to_advisory_cleanup_action():
    candidate = _factor_candidate(recommended_action="insufficient_hints")
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={candidate.proposition: _snapshot(candidate.proposition)},
    )
    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/factorization.json",
                doc=_factor_review(candidate, decision="insufficient_hints"),
            )
        ],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "cleanup_factorization_hints"
    assert action.status == "advisory"
    assert action.blockers == ()


def test_accepted_sparse_hints_maps_to_record_decision_action_with_fingerprint():
    candidate = _factor_candidate(recommended_action="insufficient_hints")
    candidate = FactorizationCandidate(
        candidate_id=candidate.candidate_id,
        proposition=candidate.proposition,
        priority="low",
        papers=candidate.papers,
        current=candidate.current,
        observed_statement_hints=candidate.observed_statement_hints,
        disagreement=("multiple assertions have insufficient factorization hints",),
        recommended_action=candidate.recommended_action,
    )
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={candidate.proposition: _snapshot(candidate.proposition)},
    )
    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/factorization.json",
                doc=_factor_review(candidate, decision="accepted_sparse_hints"),
            )
        ],
    )

    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "record_reconciliation_decision"
    assert action.status == "advisory"
    assert action.decision == "accepted_sparse_hints"
    assert action.proposition == candidate.proposition
    assert action.inputs["assertion_fingerprint"] == factorization_assertion_fingerprint(
        candidate
    )
    assert action.blockers == ()


def test_conflicting_factorization_actions_for_same_proposition_are_blocked():
    candidate = _factor_candidate()
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={candidate.proposition: _snapshot(candidate.proposition)},
    )
    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/factorization-resynthesis.json",
                doc=_factor_review(
                    candidate,
                    decision="factorization_needs_resynthesis",
                ),
            ),
            ReviewedReconciliationInput(
                path="reviews/factorization-human.json",
                doc=_factor_review(candidate, decision="needs_human"),
            ),
        ],
    )

    assert len(plan.actions) == 2
    assert {action.status for action in plan.actions} == {"blocked"}
    for action in plan.actions:
        assert any(
            blocker["reason"] == "action_conflict" for blocker in action.blockers
        )


def test_actions_are_sorted_by_action_id():
    factor_candidate = _factor_candidate()
    same_claim_report = _same_claim_report()
    report = ReconciliationReport(
        factorization_disagreements=(factor_candidate,),
        same_claim_candidates=same_claim_report.same_claim_candidates,
        faults=same_claim_report.faults,
        proposition_snapshots={
            factor_candidate.proposition: _snapshot(factor_candidate.proposition),
            **same_claim_report.proposition_snapshots,
        },
    )
    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/same-claim.json",
                doc=_same_claim_review(same_claim_report),
            ),
            ReviewedReconciliationInput(
                path="reviews/factorization.json",
                doc=_factor_review(factor_candidate),
            ),
        ],
    )

    assert [action.action_id for action in plan.actions] == sorted(
        action.action_id for action in plan.actions
    )


def test_duplicate_reviewed_actions_are_blocked_with_exact_conflict_blocker():
    candidate = _factor_candidate()
    report = ReconciliationReport(
        factorization_disagreements=(candidate,),
        proposition_snapshots={candidate.proposition: _snapshot(candidate.proposition)},
    )
    expected_blocker = {
        "reason": "action_conflict",
        "detail": "duplicate action produced by multiple reviewed inputs",
    }
    plan = build_reconciliation_action_plan(
        report,
        [
            ReviewedReconciliationInput(
                path="reviews/factorization-a.json",
                doc=_factor_review(candidate),
            ),
            ReviewedReconciliationInput(
                path="reviews/factorization-b.json",
                doc=_factor_review(candidate),
            ),
        ],
    )

    assert len(plan.actions) == 2
    for action in plan.actions:
        assert action.status == "blocked"
        assert action.blockers == (expected_blocker,)


def test_same_claim_advisory_conflicts_with_ready_canonicalization():
    report = _same_claim_report()
    candidate = report.same_claim_candidates[0]
    members = list(candidate.propositions)
    review = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id("same_claim", "same_claim", members),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": members,
                "rationale": "The propositions express the same claim.",
                "confidence": "high",
            },
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "same_claim",
                    "related_but_distinct",
                    members,
                ),
                "lane": "same_claim",
                "decision": "related_but_distinct",
                "members": members,
                "rationale": "The propositions are related but remain distinct claims.",
                "confidence": "high",
            },
        ],
    }

    plan = build_reconciliation_action_plan(
        report,
        [ReviewedReconciliationInput(path="reviews/same-claim.json", doc=review)],
    )

    assert len(plan.actions) == 2
    assert {action.status for action in plan.actions} == {"blocked"}
    for action in plan.actions:
        assert any(
            blocker["reason"] == "action_conflict" for blocker in action.blockers
        )
