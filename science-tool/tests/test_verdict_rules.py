import pytest

from science_tool.verdict.models import Claim
from science_tool.verdict.rules import aggregate_composite, rule_disagrees_with_body
from science_tool.verdict.tokens import Token


def _claim(cid: str, p: Token, w: float = 1.0) -> Claim:
    return Claim(id=cid, polarity=p, weight=w)


def test_and_rule_all_positive_yields_positive() -> None:
    claims = [_claim("c1", Token.POSITIVE), _claim("c2", Token.POSITIVE)]
    assert aggregate_composite("and", claims) == Token.POSITIVE


def test_and_rule_any_negative_yields_negative() -> None:
    claims = [_claim("c1", Token.POSITIVE), _claim("c2", Token.NEGATIVE)]
    assert aggregate_composite("and", claims) == Token.NEGATIVE


def test_and_rule_mixed_yields_mixed() -> None:
    claims = [_claim("c1", Token.POSITIVE), _claim("c2", Token.MIXED)]
    assert aggregate_composite("and", claims) == Token.MIXED


def test_or_rule_any_positive_yields_positive() -> None:
    claims = [_claim("c1", Token.POSITIVE), _claim("c2", Token.NEGATIVE)]
    assert aggregate_composite("or", claims) == Token.POSITIVE


def test_or_rule_all_negative_yields_negative() -> None:
    claims = [_claim("c1", Token.NEGATIVE), _claim("c2", Token.NEGATIVE)]
    assert aggregate_composite("or", claims) == Token.NEGATIVE


def test_or_rule_no_positive_and_not_all_negative_yields_mixed() -> None:
    claims = [_claim("c1", Token.NEGATIVE), _claim("c2", Token.MIXED)]
    assert aggregate_composite("or", claims) == Token.MIXED


def test_majority_rule_strict_three_quarters_positive_yields_positive() -> None:
    claims = [
        _claim("c1", Token.POSITIVE),
        _claim("c2", Token.POSITIVE),
        _claim("c3", Token.POSITIVE),
        _claim("c4", Token.NEGATIVE),
    ]
    assert aggregate_composite("majority", claims) == Token.POSITIVE


def test_majority_rule_strict_three_quarters_negative_yields_negative() -> None:
    claims = [
        _claim("c1", Token.NEGATIVE),
        _claim("c2", Token.NEGATIVE),
        _claim("c3", Token.NEGATIVE),
        _claim("c4", Token.POSITIVE),
    ]
    assert aggregate_composite("majority", claims) == Token.NEGATIVE


def test_majority_rule_exact_half_is_not_majority() -> None:
    claims = [
        _claim("c1", Token.POSITIVE),
        _claim("c2", Token.POSITIVE),
        _claim("c3", Token.NEGATIVE),
        _claim("c4", Token.MIXED),
    ]
    assert aggregate_composite("majority", claims) == Token.MIXED


def test_majority_rule_no_majority_yields_mixed() -> None:
    claims = [
        _claim("c1", Token.POSITIVE),
        _claim("c2", Token.NEGATIVE),
        _claim("c3", Token.MIXED),
    ]
    assert aggregate_composite("majority", claims) == Token.MIXED


def test_majority_rule_empty_claims_yields_mixed() -> None:
    assert aggregate_composite("majority", []) == Token.MIXED


def test_and_rule_empty_claims_yields_mixed() -> None:
    assert aggregate_composite("and", []) == Token.MIXED


def test_or_rule_empty_claims_yields_mixed() -> None:
    assert aggregate_composite("or", []) == Token.MIXED


def test_weighted_majority_strictly_greater_than_half_yields_that_polarity() -> None:
    claims = [
        _claim("c1", Token.NEGATIVE, 1),
        _claim("c2", Token.NEGATIVE, 1),
        _claim("c3", Token.NEGATIVE, 1),
        _claim("c4", Token.POSITIVE, 4),
    ]
    assert aggregate_composite("weighted-majority", claims) == Token.POSITIVE


def test_weighted_majority_ignores_inconclusive_weight_for_positive_winner() -> None:
    claims = [
        _claim("c1", Token.POSITIVE, 2.0),
        _claim("c2", Token.NEGATIVE, 1.5),
        _claim("c3", Token.INCONCLUSIVE, 0.5),
    ]
    assert aggregate_composite("weighted-majority", claims) == Token.POSITIVE


def test_weighted_majority_negative_adjudicating_weight_wins() -> None:
    claims = [
        _claim("c1", Token.POSITIVE, 1.5),
        _claim("c2", Token.NEGATIVE, 2.0),
        _claim("c3", Token.MIXED, 10.0),
    ]
    assert aggregate_composite("weighted-majority", claims) == Token.NEGATIVE


def test_weighted_majority_exact_half_weight_yields_mixed() -> None:
    claims = [
        _claim("c1", Token.NEGATIVE, 1),
        _claim("c2", Token.NEGATIVE, 1),
        _claim("c3", Token.NEGATIVE, 1),
        _claim("c4", Token.POSITIVE, 3),
    ]
    assert aggregate_composite("weighted-majority", claims) == Token.MIXED


def test_weighted_majority_falls_back_to_mixed_when_no_50pct() -> None:
    claims = [_claim("c1", Token.POSITIVE, 1), _claim("c2", Token.NEGATIVE, 1)]
    assert aggregate_composite("weighted-majority", claims) == Token.MIXED


def test_weighted_majority_zero_total_weight_yields_mixed() -> None:
    claims = [_claim("c1", Token.POSITIVE, 0), _claim("c2", Token.NEGATIVE, 0)]
    assert aggregate_composite("weighted-majority", claims) == Token.MIXED


def test_weighted_majority_no_adjudicating_weight_yields_mixed() -> None:
    claims = [
        _claim("c1", Token.INCONCLUSIVE, 2.0),
        _claim("c2", Token.MIXED, 1.5),
        _claim("c3", Token.NON_ADJUDICATING, 3.0),
    ]
    assert aggregate_composite("weighted-majority", claims) == Token.MIXED


def test_weighted_majority_empty_claims_yields_mixed() -> None:
    assert aggregate_composite("weighted-majority", []) == Token.MIXED


def test_bimodal_always_yields_mixed() -> None:
    claims = [_claim("c1", Token.POSITIVE), _claim("c2", Token.NEGATIVE)]
    assert aggregate_composite("bimodal", claims) == Token.MIXED


def test_non_adjudicating_always_yields_non_adjudicating() -> None:
    claims = [_claim("c1", Token.POSITIVE), _claim("c2", Token.NEGATIVE)]
    assert aggregate_composite("non-adjudicating", claims) == Token.NON_ADJUDICATING


def test_reframed_always_yields_mixed() -> None:
    claims = [_claim("c1", Token.POSITIVE), _claim("c2", Token.NEGATIVE)]
    assert aggregate_composite("reframed", claims) == Token.MIXED


def test_rule_disagrees_with_body_false_when_matching() -> None:
    assert rule_disagrees_with_body(Token.POSITIVE, Token.POSITIVE) is False


def test_rule_disagrees_with_body_true_when_mismatching() -> None:
    assert rule_disagrees_with_body(Token.NEGATIVE, Token.MIXED) is True


def test_unknown_rule_raises() -> None:
    with pytest.raises(ValueError, match="Unknown aggregation rule"):
        aggregate_composite("wat", [_claim("c1", Token.POSITIVE)])
