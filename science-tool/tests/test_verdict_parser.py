from pathlib import Path

import pytest

from science_tool.verdict.parser import NoVerdictBlockError, parse_file
from science_tool.verdict.registry import load_registry
from science_tool.verdict.tokens import Token


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "verdict"
REGISTRY_PATH = FIXTURE_DIR / "claim-registry.yaml"


def test_parse_and_fixture_hydrates_body_rule_and_claims() -> None:
    result = parse_file(FIXTURE_DIR / "doc_and.md")

    assert result.interpretation_id == "interpretation:fixture-and"
    assert result.composite_token == Token.POSITIVE
    assert result.rule == "and"
    assert result.rule_derived_composite == Token.POSITIVE
    assert result.rule_disagrees_with_body is False
    assert len(result.claims) == 2
    assert result.claims[0].id == "h1#edge5-ifn-arm"


def test_parse_majority_fixture_marks_body_rule_disagreement() -> None:
    result = parse_file(FIXTURE_DIR / "doc_majority_disagrees.md")

    assert result.composite_token == Token.MIXED
    assert result.rule_derived_composite == Token.NEGATIVE
    assert result.rule_disagrees_with_body is True


def test_parse_bimodal_fixture_derives_mixed_without_disagreement() -> None:
    result = parse_file(FIXTURE_DIR / "doc_bimodal.md")

    assert result.rule == "bimodal"
    assert result.rule_derived_composite == Token.MIXED
    assert result.rule_disagrees_with_body is False
    assert len(result.claims) == 4


def test_parse_non_adjudicating_fixture_surfaces_closure_terminal() -> None:
    result = parse_file(FIXTURE_DIR / "doc_non_adjudicating.md")

    assert result.rule == "non-adjudicating"
    assert result.composite_token == Token.NON_ADJUDICATING
    assert result.rule_disagrees_with_body is False
    assert result.closure_terminal == "non_adjudicating_under_observational_adjusters"


def test_parse_reframed_fixture_surfaces_reframing_fields() -> None:
    result = parse_file(FIXTURE_DIR / "doc_reframed.md")

    assert result.rule == "reframed"
    assert result.rule_derived_composite == Token.MIXED
    assert result.reframing_target == "interpretation:t149-ribosome-regulator-falsification"
    assert result.reframing_reason == "Raw-TPM correlations were compositional; CLR refit flipped signs."


def test_parse_weighted_majority_fixture_derives_positive_without_disagreement() -> None:
    result = parse_file(FIXTURE_DIR / "doc_weighted_majority.md")

    assert result.rule == "weighted-majority"
    assert result.rule_derived_composite == Token.POSITIVE
    assert result.rule_disagrees_with_body is False


def test_missing_frontmatter_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "missing-frontmatter.md"
    path.write_text("# Missing frontmatter\n\n**Verdict:** [+] body\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing frontmatter"):
        parse_file(path)


def test_frontmatter_without_verdict_raises_narrow_error(tmp_path: Path) -> None:
    path = tmp_path / "without-verdict.md"
    path.write_text(
        """---
id: "interpretation:missing-verdict"
---

## Verdict

**Verdict:** [+] body
""",
        encoding="utf-8",
    )

    with pytest.raises(NoVerdictBlockError, match="no 'verdict:' block"):
        parse_file(path)


def test_no_verdict_block_error_subclasses_value_error() -> None:
    assert issubclass(NoVerdictBlockError, ValueError)


def test_malformed_verdict_block_raises_vanilla_value_error() -> None:
    with pytest.raises(ValueError) as exc_info:
        parse_file(FIXTURE_DIR / "extras" / "doc_malformed_yaml.md")

    assert not isinstance(exc_info.value, NoVerdictBlockError)


def test_unknown_composite_token_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "unknown-composite.md"
    path.write_text(
        """---
id: "interpretation:unknown-composite"
verdict:
  composite: "[x]"
  rule: "and"
  claims: []
---

## Verdict

**Verdict:** [~] body
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown verdict token"):
        parse_file(path)


def test_missing_body_verdict_uses_frontmatter_composite_with_warning(tmp_path: Path) -> None:
    path = tmp_path / "missing-body-verdict.md"
    path.write_text(
        """---
id: "interpretation:missing-body-verdict"
verdict:
  composite: "[+]"
  rule: "and"
  claims:
    - id: "c1"
      polarity: "[+]"
---

## Findings

Body prose without a verdict marker.
""",
        encoding="utf-8",
    )

    result = parse_file(path)

    assert result.composite_token == Token.POSITIVE
    assert result.composite_clause == ""
    assert any("missing body verdict" in warning.lower() for warning in result.validation_warnings)


def test_invalid_body_verdict_token_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "invalid-body-verdict-token.md"
    path.write_text(
        """---
id: "interpretation:invalid-body-token"
verdict:
  composite: "[+]"
  rule: "and"
  claims:
    - id: "c1"
      polarity: "[+]"
---

## Verdict

**Verdict:** [x] bad
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown verdict token"):
        parse_file(path)


def test_invalid_first_body_verdict_token_raises_before_later_valid_verdict(tmp_path: Path) -> None:
    path = tmp_path / "invalid-first-body-token.md"
    path.write_text(
        """---
id: "interpretation:invalid-first-body-token"
verdict:
  composite: "[+]"
  rule: "and"
  claims:
    - id: "c1"
      polarity: "[+]"
---

## Verdict

**Verdict:** [x] bad

**Verdict:** [+] later
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown verdict token"):
        parse_file(path)


def test_first_body_verdict_missing_clause_raises_before_later_valid_verdict(tmp_path: Path) -> None:
    path = tmp_path / "first-body-verdict-missing-clause.md"
    path.write_text(
        """---
id: "interpretation:first-body-missing-clause"
verdict:
  composite: "[+]"
  rule: "and"
  claims:
    - id: "c1"
      polarity: "[+]"
---

## Verdict

**Verdict:** [+]

**Verdict:** [-] later
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="malformed body verdict"):
        parse_file(path)


def test_unknown_rule_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "unknown-rule.md"
    path.write_text(
        """---
id: "interpretation:unknown-rule"
verdict:
  composite: "[+]"
  rule: "wat"
  claims:
    - id: "c1"
      polarity: "[+]"
---

## Verdict

**Verdict:** [+] body
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown aggregation rule"):
        parse_file(path)


def test_registry_resolution_has_no_unresolved_claims_for_registered_fixture() -> None:
    registry = load_registry(REGISTRY_PATH)

    result = parse_file(FIXTURE_DIR / "doc_and.md", registry=registry)

    assert result.unresolved_claim_ids == []
    assert all("unresolved" not in warning.lower() for warning in result.validation_warnings)


def test_registry_resolution_reports_unresolved_claim_ids() -> None:
    registry = load_registry(REGISTRY_PATH)

    result = parse_file(FIXTURE_DIR / "extras" / "doc_unresolved_claim.md", registry=registry)

    assert result.unresolved_claim_ids == ["hunknown#not-in-registry"]
    assert any("unresolved" in warning.lower() for warning in result.validation_warnings)


def test_registry_resolution_reports_one_warning_per_unresolved_claim(tmp_path: Path) -> None:
    path = tmp_path / "two-unresolved-claims.md"
    path.write_text(
        """---
id: "interpretation:two-unresolved"
verdict:
  composite: "[+]"
  rule: "and"
  claims:
    - id: "hunknown#first"
      polarity: "[+]"
    - id: "hunknown#second"
      polarity: "[+]"
---

## Verdict

**Verdict:** [+] body
""",
        encoding="utf-8",
    )
    registry = load_registry(REGISTRY_PATH)

    result = parse_file(path, registry=registry)
    unresolved_warnings = [warning for warning in result.validation_warnings if "unresolved" in warning.lower()]

    assert result.unresolved_claim_ids == ["hunknown#first", "hunknown#second"]
    assert len(unresolved_warnings) == 2
    assert any("hunknown#first" in warning for warning in unresolved_warnings)
    assert any("hunknown#second" in warning for warning in unresolved_warnings)


def test_without_registry_unresolved_fixture_keeps_unresolved_claim_ids_empty() -> None:
    result = parse_file(FIXTURE_DIR / "extras" / "doc_unresolved_claim.md")

    assert result.unresolved_claim_ids == []
