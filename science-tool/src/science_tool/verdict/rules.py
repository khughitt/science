"""Aggregation rules for deriving composite verdict tokens from claims."""

from __future__ import annotations

from collections import Counter

from science_tool.verdict.models import Claim
from science_tool.verdict.tokens import Token


def aggregate_composite(rule: str, claims: list[Claim]) -> Token:
    """Return the rule-derived composite token for a list of claims."""
    counts = Counter(claim.polarity for claim in claims)

    if rule == "and":
        return _aggregate_and(counts, len(claims))
    if rule == "or":
        return _aggregate_or(counts, len(claims))
    if rule == "majority":
        return _aggregate_majority(counts, len(claims))
    if rule == "weighted-majority":
        return _rule_weighted_majority(claims)
    if rule == "bimodal":
        return Token.MIXED
    if rule == "non-adjudicating":
        return Token.NON_ADJUDICATING
    if rule == "reframed":
        return Token.MIXED
    raise ValueError(f"Unknown aggregation rule: {rule!r}")


def rule_disagrees_with_body(rule_composite: Token, body_composite: Token) -> bool:
    """Return True when the rule-derived composite differs from the body verdict."""
    return rule_composite != body_composite


def _aggregate_and(counts: Counter[Token], claim_count: int) -> Token:
    if claim_count == 0:
        return Token.MIXED
    if counts[Token.NEGATIVE] > 0:
        return Token.NEGATIVE
    if counts[Token.POSITIVE] == claim_count:
        return Token.POSITIVE
    return Token.MIXED


def _aggregate_or(counts: Counter[Token], claim_count: int) -> Token:
    if claim_count == 0:
        return Token.MIXED
    if counts[Token.POSITIVE] > 0:
        return Token.POSITIVE
    if counts[Token.NEGATIVE] == claim_count:
        return Token.NEGATIVE
    return Token.MIXED


def _aggregate_majority(counts: Counter[Token], claim_count: int) -> Token:
    if claim_count == 0:
        return Token.MIXED
    if counts[Token.POSITIVE] / claim_count > 0.5:
        return Token.POSITIVE
    if counts[Token.NEGATIVE] / claim_count > 0.5:
        return Token.NEGATIVE
    return Token.MIXED


def _rule_weighted_majority(claims: list[Claim]) -> Token:
    positive_weight = 0.0
    negative_weight = 0.0
    unresolved_weight = 0.0
    for claim in claims:
        if claim.polarity == Token.POSITIVE:
            positive_weight += claim.weight
        elif claim.polarity == Token.NEGATIVE:
            negative_weight += claim.weight
        else:
            unresolved_weight += claim.weight

    adjudicating_weight = positive_weight + negative_weight
    if adjudicating_weight <= 0:
        return Token.MIXED

    if unresolved_weight > 0 and (positive_weight <= 0 or negative_weight <= 0):
        return Token.MIXED

    if positive_weight / adjudicating_weight > 0.5:
        return Token.POSITIVE
    if negative_weight / adjudicating_weight > 0.5:
        return Token.NEGATIVE
    return Token.MIXED
