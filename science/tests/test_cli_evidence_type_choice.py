from click.testing import CliRunner

from science_tool.cli import EVIDENCE_TYPES, main


def test_evidence_types_reconciles_with_enum():
    from science_model.reasoning import EvidenceType, canonical_evidence_type_token

    assert {canonical_evidence_type_token(t) for t in EVIDENCE_TYPES} == {m.value for m in EvidenceType}


def test_cli_rejects_out_of_vocab_evidence_type():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["graph", "add", "proposition", "P text", "--source", "t1",
         "--evidence-type", "differential_expression"],
        catch_exceptions=False,
    )
    # click.Choice rejects before any graph work -> usage error (exit code 2).
    assert result.exit_code == 2
    assert "differential_expression" in result.output
