import pytest

from science_tool.correspondence.adjudicate import Adjudicated
from science_tool.drift_sample.score import (
    GateOutcome, cp_upper, gate, manski, verdict,
)
from science_tool.drift_sample.normalize import normalize_claim


# --- claim normalization (design §6.2a) ---

@pytest.mark.parametrize("claimed,expected", [
    ("draft", "draft"), ("active", "active"), ("complete", "complete"),
    ("superseded", "superseded"), ("retired", "retired"), ("archived", "archived"),
    ("proposed", "draft"), ("design", "draft"),
    ("implemented", "complete"), ("completed", "complete"),
    ("in-progress", "active"), ("current", "active"), ("agreed", "active"),
])
def test_normalize_maps_prescribed_synonyms(claimed: str, expected: str):
    assert normalize_claim(claimed) == expected


@pytest.mark.parametrize("claimed", ["approved", "draft-for-review", "ready-with-caveats", "not-ready"])
def test_unmappable_claims_return_none(claimed: str):
    """These are S4's open question. Mapping them would decide S4 inside S1's evidence."""
    assert normalize_claim(claimed) is None


def test_unknown_claim_value_is_unmappable_not_an_error():
    assert normalize_claim("something-nobody-predeclared") is None


# --- verdict ---

def test_match_is_not_a_mismatch():
    assert verdict("draft", Adjudicated.DRAFT) is False


def test_stale_under_claim_is_a_mismatch():
    """The S1 §2.2 hypothesis: claims draft, everything shipped."""
    assert verdict("draft", Adjudicated.COMPLETE) is True


def test_over_claim_is_a_mismatch():
    assert verdict("complete", Adjudicated.DRAFT) is True


def test_synonym_claim_matches_after_normalization():
    """`implemented` vs COMPLETE is a vocabulary issue (S4), not drift."""
    assert verdict("implemented", Adjudicated.COMPLETE) is False


def test_indeterminate_adjudication_is_indeterminate():
    assert verdict("draft", Adjudicated.INDETERMINATE) is None


def test_unmappable_claim_is_indeterminate():
    assert verdict("approved", Adjudicated.COMPLETE) is None


# --- Manski bounds (design §6.3) ---

def test_manski_bounds_bracket_the_indeterminates():
    # 2 mismatches, 3 matches, 2 indeterminate
    v = [True, True, False, False, False, None, None]
    assert manski(v) == (2, 4)


def test_manski_bounds_coincide_when_nothing_indeterminate():
    assert manski([True, False, False]) == (1, 1)


# --- gate (design §7) ---

def test_gate_rules_out_only_at_zero_errors_at_40():
    assert gate(0, 40) is GateOutcome.RULE_OUT
    assert gate(1, 40) is GateOutcome.CONTINUE


def test_gate_demonstrates_at_40():
    assert gate(9, 40) is GateOutcome.DEMONSTRATE
    assert gate(8, 40) is GateOutcome.CONTINUE


def test_gate_at_80():
    assert gate(2, 80) is GateOutcome.RULE_OUT
    assert gate(3, 80) is GateOutcome.CONTINUE
    assert gate(15, 80) is GateOutcome.DEMONSTRATE


def test_gate_at_census_compares_directly():
    """At n = N the rate is observed, not estimated."""
    assert gate(26, 264) is GateOutcome.RULE_OUT     # 9.8% < 10%
    assert gate(27, 264) is GateOutcome.DEMONSTRATE  # 10.2% > 10%


def test_rule_out_is_unreachable_below_the_ladder_floor():
    """At n = 29 even zero errors cannot clear theta -- why the ladder starts at 40."""
    assert cp_upper(0, 29, 0.05 / 3) > 0.10
    assert cp_upper(0, 39, 0.05 / 3) < 0.10


def test_gate_rejects_an_unregistered_sample_size():
    """Only the predeclared looks exist; an ad-hoc n is optional stopping."""
    with pytest.raises(ValueError, match="not a predeclared look"):
        gate(1, 55)
