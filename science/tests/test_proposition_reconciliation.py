import hashlib

import pytest

from science_tool.annotation.proposition_reconciliation import (
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
