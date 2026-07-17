"""The strict loader's projection of the arbitration ledger onto exceptions.

The boundary decides RAISE vs REPORT. It must be total over the ledger's vocabulary: a code it
does not recognize is a code whose strictness nobody chose, and the failure mode of matching on
bare strings is silence -- the load returns success for a defect arbitration positively found.
"""
from __future__ import annotations

import pytest
from science_model.source_ref import SourceRef

from science_tool.graph.errors import ContributionConflictError, EntityIdentityCollisionError
from science_tool.graph.identity_arbitration import ArbitrationCode, ArbitrationError
from science_tool.graph.sources import _raise_first_arbitration_error


def _error(code: ArbitrationCode, *, field: str = "", refs: int = 2) -> ArbitrationError:
    return ArbitrationError(
        code=code,
        canonical_id="paper:x",
        owner_scope="proj",
        field=field,
        contributors=tuple(
            SourceRef(adapter_name="markdown", path=f"entities/papers/{i}.md", line=None)
            for i in range(refs)
        ),
    )


def test_duplicate_owner_raises_the_identity_collision() -> None:
    with pytest.raises(EntityIdentityCollisionError):
        _raise_first_arbitration_error([_error(ArbitrationCode.DUPLICATE_OWNER)])


def test_contribution_conflict_raises_with_structured_refs() -> None:
    with pytest.raises(ContributionConflictError) as caught:
        _raise_first_arbitration_error([_error(ArbitrationCode.CONTRIBUTION_CONFLICT, field="doi")])
    # Structured, not parsed back out of a rendered message.
    assert caught.value.field == "doi"
    assert [ref.path for ref in caught.value.refs] == ["entities/papers/0.md", "entities/papers/1.md"]


@pytest.mark.parametrize("code", [ArbitrationCode.MISSING_OWNER, ArbitrationCode.AMBIGUOUS_REPRESENTATIVE])
def test_reportable_codes_do_not_raise(code: ArbitrationCode) -> None:
    # Deliberately diagnostic: both already suppress materialization, so the graph never shows a
    # guessed answer. They must reach the audit rather than abort the load.
    _raise_first_arbitration_error([_error(code)])


def test_every_code_in_the_vocabulary_has_a_decided_disposition() -> None:
    """The totality guard. Adding a fifth code must break THIS test, not go silently unraised.

    Without it, a new code inherits "do not raise" from the fall-through -- the strict loader
    would keep reporting success for a defect the ledger recorded, which is the precise failure
    this whole arc exists to remove.
    """
    for code in ArbitrationCode:
        raised = None
        try:
            _raise_first_arbitration_error([_error(code)])
        except (EntityIdentityCollisionError, ContributionConflictError) as exc:
            raised = exc
        assert (raised is not None) == (code in _RAISING), (
            f"{code} has no decided disposition at the strict boundary"
        )


_RAISING = {ArbitrationCode.DUPLICATE_OWNER, ArbitrationCode.CONTRIBUTION_CONFLICT}
