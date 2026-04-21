from science_tool.verdict.tokens import Token, parse_body_verdict


def test_token_enum_has_five_values() -> None:
    assert {t.value for t in Token} == {"[+]", "[-]", "[~]", "[?]", "[⌀]"}


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


def test_parse_body_verdict_takes_first_match() -> None:
    md = "**Verdict:** [+] first\n\n**Verdict:** [-] later line should be ignored\n"
    tok, clause = parse_body_verdict(md)
    assert tok == Token.POSITIVE
    assert clause == "first"
