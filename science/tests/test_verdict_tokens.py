import pytest

from science_tool.verdict.tokens import Token, parse_body_verdict


def test_token_enum_has_five_values() -> None:
    assert {t.value for t in Token} == {"[+]", "[-]", "[~]", "[?]", "[⌀]"}


def test_token_from_str_returns_matching_token() -> None:
    assert Token.from_str("[+]") == Token.POSITIVE


def test_token_from_str_raises_for_unknown_token() -> None:
    with pytest.raises(ValueError, match=r"Unknown verdict token: '\[x\]'"):
        Token.from_str("[x]")


def test_parse_body_verdict_finds_first_line() -> None:
    md = """# Some Interpretation

## Verdict

**Verdict:** [+] The prediction held with p < 0.01.

## Summary

further prose here...
"""
    assert parse_body_verdict(md) == (Token.POSITIVE, "The prediction held with p < 0.01.")


def test_parse_body_verdict_handles_non_adjudicating() -> None:
    md = "\n**Verdict:** [⌀] Non-adjudicating terminal.\n"
    assert parse_body_verdict(md) == (Token.NON_ADJUDICATING, "Non-adjudicating terminal.")


def test_parse_body_verdict_returns_none_when_missing() -> None:
    assert parse_body_verdict("# Doc with no verdict\n\nprose\n") is None


def test_parse_body_verdict_does_not_consume_next_section_when_clause_missing() -> None:
    assert parse_body_verdict("**Verdict:** [+]\n\n## Summary\nbody") is None
    assert parse_body_verdict("**Verdict:** [+]   \n\n## Summary\nbody") is None


def test_parse_body_verdict_takes_first_match() -> None:
    md = "**Verdict:** [+] first\n\n**Verdict:** [-] later line should be ignored\n"
    result = parse_body_verdict(md)
    assert result is not None
    tok, clause = result
    assert tok == Token.POSITIVE
    assert clause == "first"
