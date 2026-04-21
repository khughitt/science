from dataclasses import asdict

from science_tool.verdict.models import (
    Claim,
    Context,
    ParseResult,
    VerdictBlock,
)
from science_tool.verdict.tokens import Token


def test_verdict_block_minimal_construction() -> None:
    block = VerdictBlock(composite=Token.POSITIVE, rule="and", claims=[])
    assert block.composite == Token.POSITIVE
    assert block.rule == "and"
    assert block.claims == []
    assert block.closure_terminal is None
    assert block.reframing_target is None


def test_claim_with_contexts_and_weight() -> None:
    c = Claim(
        id="h1#edge5-ifn-arm",
        polarity=Token.POSITIVE,
        strength="strong",
        weight=1.5,
        evidence_summary="NES=+2.83 padj<1e-15",
        contexts=[
            Context(context="MM.1S", polarity=Token.POSITIVE, strength="strong"),
            Context(context="RPMI-8226", polarity=Token.POSITIVE, strength="strong"),
        ],
    )
    assert c.weight == 1.5
    assert len(c.contexts) == 2
    assert c.contexts[0].context == "MM.1S"


def test_parse_result_roundtrips_to_dict() -> None:
    result = ParseResult(
        interpretation_id="interpretation:2026-04-14-t197",
        composite_token=Token.MIXED,
        composite_clause="Weakly_replicated; IFN both, E2F partial.",
        rule="and",
        rule_derived_composite=Token.MIXED,
        rule_disagrees_with_body=False,
        claims=[
            Claim(
                id="h1#edge5-ifn-arm",
                polarity=Token.POSITIVE,
                strength="strong",
                weight=1.0,
                evidence_summary="",
                contexts=[],
            )
        ],
        validation_warnings=[],
    )
    d = asdict(result)
    assert d["interpretation_id"] == "interpretation:2026-04-14-t197"
    assert d["rule_disagrees_with_body"] is False
    assert d["claims"][0]["id"] == "h1#edge5-ifn-arm"
    assert d["closure_terminal"] is None


def test_parse_result_surfaces_closure_terminal_and_reframing_fields() -> None:
    result = ParseResult(
        interpretation_id="interpretation:fake",
        composite_token=Token.NON_ADJUDICATING,
        composite_clause="closed under observational adjusters",
        rule="non-adjudicating",
        rule_derived_composite=Token.NON_ADJUDICATING,
        rule_disagrees_with_body=False,
        closure_terminal="non_adjudicating_under_observational_adjusters",
        reframing_target="interpretation:t149-original-finding",
        reframing_reason="raw-TPM correlations were compositional",
    )
    assert result.closure_terminal == "non_adjudicating_under_observational_adjusters"
    assert result.reframing_target == "interpretation:t149-original-finding"
    assert result.reframing_reason == "raw-TPM correlations were compositional"
    d = asdict(result)
    assert d["closure_terminal"] == "non_adjudicating_under_observational_adjusters"
    assert d["reframing_target"] == "interpretation:t149-original-finding"
    assert d["reframing_reason"] == "raw-TPM correlations were compositional"
