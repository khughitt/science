import hashlib

import pytest

from science_tool.annotation.cross_paper_evidence import LiteratureAssertion
from science_tool.annotation.proposition_reconciliation import (
    FactorizationCandidate,
    MAX_RECONCILIATION_COMPONENT_SIZE,
    PropositionSnapshot,
    ReconciliationReport,
    ReconciliationValidationError,
    build_factorization_disagreements,
    build_same_claim_candidates,
    candidate_id,
    candidate_to_json,
    judgment_id,
    normalize_phrase,
    polarity_compatible,
    predicate_compatible,
    report_to_json,
    resolve_review_doc,
    title_tokens,
    validate_review_doc,
)


def test_candidate_id_uses_full_sha256_of_lane_and_sorted_refs():
    expected = hashlib.sha256(b"same_claim\x00proposition:a\x00proposition:b").hexdigest()
    assert candidate_id("same_claim", ["proposition:b", "proposition:a"]) == (
        f"reconcile:same-claim/{expected}"
    )


def test_candidate_id_rejects_unknown_lane():
    with pytest.raises(ValueError, match="unknown reconciliation lane"):
        candidate_id("typo", ["proposition:a"])


def test_judgment_id_uses_lane_decision_and_sorted_member_set():
    expected = hashlib.sha256(
        b"same_claim\x00same_claim\x00proposition:a\x00proposition:b"
    ).hexdigest()
    assert judgment_id("same_claim", "same_claim", ["proposition:b", "proposition:a"]) == (
        f"reconcile:judgment/{expected}"
    )


def test_normalize_phrase_casefolds_and_collapses_whitespace():
    assert normalize_phrase("  BRCA1   Loss ") == "brca1 loss"


def test_predicate_compatibility_is_small_and_enum_tied():
    assert predicate_compatible("affects", "affects") is True
    assert predicate_compatible("affects", "regulates") is True
    assert predicate_compatible("associates_with", "regulates") is True
    assert predicate_compatible("subtype_of", "part_of") is False
    assert predicate_compatible("induces_state", "transitions_to") is False
    assert predicate_compatible(None, "affects") is False


def test_polarity_compatibility_allows_unsigned_but_not_opposite_signs():
    assert polarity_compatible("positive", "positive") is True
    assert polarity_compatible("positive", "unsigned") is True
    assert polarity_compatible("negative", "unsigned") is True
    assert polarity_compatible("positive", "negative") is False
    assert polarity_compatible("not_applicable", "not_applicable") is True


def test_title_tokens_remove_stopwords_and_short_tokens():
    assert title_tokens("The BRCA1 loss affects genomic instability in cells") == {
        "brca1",
        "loss",
        "affects",
        "genomic",
        "instability",
        "cells",
    }


def _prop(
    ref: str,
    title: str,
    *,
    subject: str | None = "BRCA1 loss",
    predicate: str | None = "affects",
    object: str | None = "genomic instability",
    polarity: str | None = "positive",
    papers: frozenset[str] = frozenset(),
) -> PropositionSnapshot:
    return PropositionSnapshot(
        ref=ref,
        title=title,
        subject=subject,
        predicate=predicate,
        object=object,
        polarity=polarity,
        source_refs=frozenset(papers),
        paper_refs=frozenset(papers),
    )


def test_same_claim_structured_match_high_priority():
    report = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
        ]
    )

    assert report.faults == ()
    assert len(report.candidates) == 1
    candidate = report.candidates[0]
    assert candidate.propositions == ("proposition:a", "proposition:b")
    assert candidate.priority == "high"
    assert candidate.splittable is False
    assert candidate.signals["same_subject"] is True
    assert candidate.signals["predicate_compatible"] is True


def test_same_claim_opposite_polarity_is_conflict_flag_not_same_claim_merge():
    report = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability", polarity="positive"),
            _prop("proposition:b", "BRCA1 loss decreases genomic instability", polarity="negative"),
        ]
    )

    assert len(report.candidates) == 1
    candidate = report.candidates[0]
    assert "conflict_or_negation" in candidate.flags
    assert candidate.priority == "medium"


def test_missing_factorization_with_shared_paper_and_high_title_overlap_is_low_priority():
    report = build_same_claim_candidates(
        [
            _prop(
                "proposition:a",
                "BRCA1 loss increases genomic instability",
                subject=None,
                predicate=None,
                object=None,
                polarity=None,
                papers=frozenset({"paper:A2020"}),
            ),
            _prop(
                "proposition:b",
                "BRCA1 loss raises genomic instability",
                subject=None,
                predicate=None,
                object=None,
                polarity=None,
                papers=frozenset({"paper:A2020"}),
            ),
        ]
    )

    assert len(report.candidates) == 1
    assert report.candidates[0].priority == "low"
    assert "needs_factorization_context" in report.candidates[0].flags


def test_connected_component_groups_pairs_deterministically():
    report = build_same_claim_candidates(
        [
            _prop("proposition:c", "claim c"),
            _prop("proposition:a", "claim a"),
            _prop("proposition:b", "claim b"),
        ]
    )

    assert len(report.candidates) == 1
    assert report.candidates[0].propositions == ("proposition:a", "proposition:b", "proposition:c")
    assert report.candidates[0].splittable is True


def test_large_component_faults_instead_of_scaffolding():
    props = [
        _prop(f"proposition:p{i:02d}", f"claim {i}", papers=frozenset({"paper:A2020"}))
        for i in range(MAX_RECONCILIATION_COMPONENT_SIZE + 1)
    ]
    report = build_same_claim_candidates(props)

    assert report.candidates == ()
    assert len(report.faults) == 1
    assert report.faults[0].reason == "component-too-large"


def _assertion(
    frag: str,
    *,
    proposition_ref: str = "proposition:p",
    paper_ref: str = "paper:A2020",
    stance: str = "asserted",
    subject: str | None = "BRCA1 loss",
    object: str | None = "genomic instability",
) -> LiteratureAssertion:
    citekey = paper_ref.split(":", 1)[1]
    return LiteratureAssertion(
        proposition_ref=proposition_ref,
        paper_ref=paper_ref,
        stance=stance,
        annotation_id=frag,
        sidecar=f"{paper_ref}.anno.trig",
        annotation_ref=f"annotation:entities/papers/{citekey}.source#{frag}",
        statement_exact=f"{subject or 'claim'} -> {object or 'target'}",
        section="results",
        subject=subject,
        object=object,
    )


def test_factorization_disagreement_detects_incompatible_objects():
    prop = _prop("proposition:p", "BRCA1 loss affects genome stability")
    candidates = build_factorization_disagreements(
        {"proposition:p": prop},
        [
            _assertion("a1", object="genomic instability"),
            _assertion("a2", paper_ref="paper:B2021", object="replication stress"),
        ],
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.proposition == "proposition:p"
    assert candidate.recommended_action == "factorization_needs_resynthesis"
    assert "object differs" in candidate.disagreement
    assert len(candidate.observed_statement_hints) == 2


def test_factorization_disagreement_detects_mixed_stances():
    prop = _prop("proposition:p", "BRCA1 loss affects genome stability")
    candidates = build_factorization_disagreements(
        {"proposition:p": prop},
        [
            _assertion("a1", stance="asserted"),
            _assertion("a2", paper_ref="paper:B2021", stance="negated"),
        ],
    )

    assert len(candidates) == 1
    assert candidates[0].recommended_action == "stance_review_needed"
    assert "stance mix requires review" in candidates[0].disagreement


def test_factorization_disagreement_detects_unfactored_multiple_useful_hints():
    prop = _prop(
        "proposition:p",
        "BRCA1 loss affects genome stability",
        subject=None,
        predicate=None,
        object=None,
        polarity=None,
    )
    candidates = build_factorization_disagreements(
        {"proposition:p": prop},
        [_assertion("a1"), _assertion("a2", paper_ref="paper:B2021")],
    )

    assert len(candidates) == 1
    assert candidates[0].recommended_action == "factorization_needs_resynthesis"
    assert (
        "current proposition is unfactored despite useful statement hints"
        in candidates[0].disagreement
    )


def test_candidate_to_json_keeps_stable_public_shape():
    candidate = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
        ]
    ).candidates[0]

    payload = candidate_to_json(candidate)

    assert payload["candidate_id"].startswith("reconcile:same-claim/")
    assert payload["propositions"] == ["proposition:a", "proposition:b"]
    assert payload["priority"] == "high"
    assert payload["splittable"] is False
    assert payload["flags"] == []
    assert "pair_edges" not in payload


def test_report_to_json_includes_summary_counts():
    same = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
        ]
    )
    report = ReconciliationReport(same_claim_candidates=same.candidates, faults=same.faults)

    payload = report_to_json(report)

    assert payload["summary"]["same_claim_candidates"] == 1
    assert payload["summary"]["factorization_disagreements"] == 0
    assert payload["summary"]["faults"] == 0


def _candidate_report() -> ReconciliationReport:
    same = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
        ]
    )
    return ReconciliationReport(same_claim_candidates=same.candidates)


def test_validate_review_doc_accepts_same_claim_judgment():
    report = _candidate_report()
    candidate = report.same_claim_candidates[0]
    doc = {
        "source": "llm-review:claude-opus-4-8:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", list(candidate.propositions)
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": list(candidate.propositions),
                "rationale": (
                    "The claims share endpoints, predicate, polarity, and assertion meaning."
                ),
                "confidence": "high",
            }
        ],
    }

    result = validate_review_doc(doc, report)

    assert result["status"] == "ok"
    assert result["judgments"] == 1
    assert result["errors"] == []


def test_validate_review_doc_reanchors_splittable_subset_after_component_growth():
    current = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
            _prop("proposition:c", "BRCA1 loss promotes genomic instability"),
        ]
    )
    report = ReconciliationReport(same_claim_candidates=current.candidates)
    old_pair_candidate_id = candidate_id("same_claim", ["proposition:a", "proposition:b"])
    doc = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": old_pair_candidate_id,
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", ["proposition:a", "proposition:b"]
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": ["proposition:a", "proposition:b"],
                "rationale": (
                    "The pair remains the same claim even though the current component grew."
                ),
                "confidence": "high",
            }
        ],
    }

    result = validate_review_doc(doc, report)

    assert result["status"] == "ok"
    assert result["review_incomplete"] == [
        {
            "candidate_id": report.same_claim_candidates[0].candidate_id,
            "missing": ["proposition:c"],
        }
    ]


def test_validate_review_doc_rejects_wrong_subset_candidate_id():
    current = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
            _prop("proposition:c", "BRCA1 loss promotes genomic instability"),
        ]
    )
    report = ReconciliationReport(same_claim_candidates=current.candidates)
    doc = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate_id("same_claim", ["proposition:a", "proposition:c"]),
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", ["proposition:a", "proposition:b"]
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": ["proposition:a", "proposition:b"],
                "rationale": "The member set is real but the candidate anchor is not.",
                "confidence": "high",
            }
        ],
    }

    with pytest.raises(ReconciliationValidationError, match="candidate_id"):
        validate_review_doc(doc, report)


@pytest.mark.parametrize(
    "bad_source",
    [
        "llm-review:<MODEL>:proposition-reconcile-v1",
        "llm-synth:claude:proposition-reconcile-v1",
        "llm-review:claude opus:proposition-reconcile-v1",
    ],
)
def test_validate_review_doc_rejects_bad_source(bad_source: str):
    report = _candidate_report()
    candidate = report.same_claim_candidates[0]
    doc = {
        "source": bad_source,
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", list(candidate.propositions)
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": list(candidate.propositions),
                "rationale": "valid rationale",
                "confidence": "high",
            }
        ],
    }

    with pytest.raises(ReconciliationValidationError, match="source"):
        validate_review_doc(doc, report)


def test_validate_review_doc_rejects_wrong_judgment_id():
    report = _candidate_report()
    candidate = report.same_claim_candidates[0]
    doc = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": "reconcile:judgment/not-the-right-hash",
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": list(candidate.propositions),
                "rationale": "valid rationale",
                "confidence": "high",
            }
        ],
    }

    with pytest.raises(ReconciliationValidationError, match="judgment_id"):
        validate_review_doc(doc, report)


def test_validate_review_doc_rejects_lane_b_same_claim_decision():
    factor = FactorizationCandidate(
        candidate_id=candidate_id("factorization_disagreement", ["proposition:p"]),
        proposition="proposition:p",
        priority="medium",
        papers=("paper:A2020",),
        current={},
        observed_statement_hints=(),
        disagreement=("object differs",),
        recommended_action="factorization_needs_resynthesis",
    )
    report = ReconciliationReport(factorization_disagreements=(factor,))
    doc = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": factor.candidate_id,
                "judgment_id": judgment_id(
                    "factorization_disagreement", "same_claim", ["proposition:p"]
                ),
                "lane": "factorization_disagreement",
                "decision": "same_claim",
                "proposition": "proposition:p",
                "rationale": "valid rationale",
                "confidence": "medium",
            }
        ],
    }

    with pytest.raises(ReconciliationValidationError, match="Lane B"):
        validate_review_doc(doc, report)


def test_reconciliation_report_can_carry_proposition_snapshots():
    snapshot = _prop(
        "proposition:a",
        "BRCA1 loss increases genomic instability",
        papers=frozenset({"paper:A2020"}),
    )
    report = ReconciliationReport(proposition_snapshots={snapshot.ref: snapshot})

    assert report.proposition_snapshots == {"proposition:a": snapshot}


def test_resolve_review_doc_returns_candidate_and_validation_payload():
    report = _candidate_report()
    candidate = report.same_claim_candidates[0]
    doc = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "same_claim", "same_claim", list(candidate.propositions)
                ),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": "proposition:a",
                "members": list(candidate.propositions),
                "rationale": "Same signed relation over same endpoints.",
                "confidence": "high",
            }
        ],
    }

    resolved = resolve_review_doc(doc, report)

    assert resolved.validation["status"] == "ok"
    assert resolved.validation["review_incomplete"] == []
    assert len(resolved.judgments) == 1
    assert resolved.judgments[0].candidate == candidate
    assert resolved.judgments[0].judgment["decision"] == "same_claim"


def test_resolve_review_doc_preserves_review_incomplete_payload():
    current = build_same_claim_candidates(
        [
            _prop("proposition:a", "BRCA1 loss increases genomic instability"),
            _prop("proposition:b", "Loss of BRCA1 raises genome instability"),
            _prop("proposition:c", "BRCA1 loss promotes genomic instability"),
        ]
    )
    report = ReconciliationReport(same_claim_candidates=current.candidates)
    doc = {
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
                "rationale": "The pair is a same-claim subset of the current component.",
                "confidence": "high",
            }
        ],
    }

    resolved = resolve_review_doc(doc, report)

    assert resolved.validation["review_incomplete"] == [
        {
            "candidate_id": report.same_claim_candidates[0].candidate_id,
            "missing": ["proposition:c"],
        }
    ]
    assert resolved.judgments[0].candidate == report.same_claim_candidates[0]
