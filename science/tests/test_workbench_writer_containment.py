"""Writer containment: what the workbench persists must satisfy the durable base contract.

The boundary rule (design §5.1): empty fields may be acceptable while constructing an in-memory
entity; they are NOT acceptable once persisted as authored source. `workbench.py` used to cite the
entity-model tests' minimal-construction pattern as precedent for a production write.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.reasoning import EvidenceType
from science_tool.dag.workbench import (
    EvidenceStub,
    WorkbenchRow,
    _evidence_line_for_stub,
    _proposition_for_row,
)


def _row(**over) -> WorkbenchRow:
    # `polarity` is REQUIRED here: `affects` is sign-meaningful, and `PropositionEntity` rejects it
    # without positive/negative/unsigned. Omitting it makes every test below fail during fixture
    # construction, before any title assertion is reached.
    base = {
        "subject": "concept:a",
        "predicate": "affects",
        "object": "concept:b",
        "patch": "p",
        "polarity": "unsigned",
    }
    return WorkbenchRow(**{**base, **over})


def test_proposition_title_is_the_triple() -> None:
    # THE RULING (design §5.2). Deterministic generation, not a required input field: `WorkbenchRow`
    # is extra="forbid" and carries no `title`, so requiring one would widen the authored-input
    # contract. Changing this string is a behaviour change and must fail here.
    prop = _proposition_for_row(_row())
    assert prop.title == "concept:a affects concept:b"


def test_evidence_line_title_uses_source_when_present() -> None:
    stub = EvidenceStub(stance="supports", source="paper:Smith2025")
    line = _evidence_line_for_stub(stub, target_id="proposition:0001-x", index=0)
    assert line.title == "supports proposition:0001-x — paper:Smith2025"


def test_evidence_line_title_falls_back_to_evidence_type() -> None:
    stub = EvidenceStub(stance="disputes", evidence_type=EvidenceType.LITERATURE)
    line = _evidence_line_for_stub(stub, target_id="proposition:0001-x", index=0)
    assert line.title == "disputes proposition:0001-x — literature"


def test_evidence_line_title_without_qualifiers_is_still_non_empty() -> None:
    # `target_id` is computed and always present, so the head alone satisfies minLength: 1 even
    # when the stub carries no stance, source or evidence_type.
    line = _evidence_line_for_stub(EvidenceStub(), target_id="proposition:0001-x", index=0)
    assert line.title == "supports proposition:0001-x"


def test_generated_titles_are_whitespace_collapsed() -> None:
    prop = _proposition_for_row(_row(subject="concept:a  b", object="concept:c\td"))
    assert prop.title == "concept:a b affects concept:c d"


@pytest.mark.parametrize("field", ["subject", "object"])
def test_empty_triple_terms_fail_at_PARSE_time(field: str) -> None:
    # Not at title construction, and not at base validation. `predicate` is already protected by
    # the `Predicate("")` conversion; subject and object were not protected by anything.
    with pytest.raises(ValidationError):
        _row(**{field: ""})
