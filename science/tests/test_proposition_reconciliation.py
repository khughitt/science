import hashlib

import pytest

from science_tool.annotation.proposition_reconciliation import (
    MAX_RECONCILIATION_COMPONENT_SIZE,
    PropositionSnapshot,
    build_same_claim_candidates,
    candidate_id,
    judgment_id,
    normalize_phrase,
    polarity_compatible,
    predicate_compatible,
    title_tokens,
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
