import pytest
from pydantic import ValidationError

from science_tool.cli import EVIDENCE_TYPES
from science_tool.dag.workbench import EvidenceStub


def test_evidence_types_reconciles_with_enum():
    from science_model.reasoning import EvidenceType, canonical_evidence_type_token

    assert {canonical_evidence_type_token(t) for t in EVIDENCE_TYPES} == {m.value for m in EvidenceType}


def test_source_authored_evidence_rejects_out_of_vocab_evidence_type():
    with pytest.raises(ValidationError, match="differential_expression"):
        EvidenceStub.model_validate({"stance": "supports", "evidence_type": "differential_expression"})
