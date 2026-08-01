"""The two title derivations shared by the workbench writer and the base-shape migration."""

from __future__ import annotations

import pytest
from science_model.reasoning import EvidenceType

from science_tool.dag.entity_frontmatter import (
    derive_evidence_line_title,
    derive_proposition_title,
)


def test_proposition_title_is_the_collapsed_triple():
    assert (
        derive_proposition_title(subject="concept:a", predicate="affects", object="concept:b")
        == "concept:a affects concept:b"
    )


def test_proposition_title_collapses_internal_whitespace():
    assert (
        derive_proposition_title(subject="concept:a  b", predicate="affects\n", object="concept:c")
        == "concept:a b affects concept:c"
    )


def test_evidence_line_title_prefers_source_for_the_tail():
    assert (
        derive_evidence_line_title(
            stance="supports",
            target_id="proposition:p",
            source="paper:Walker2024",
            evidence_type="literature_evidence",
        )
        == "supports proposition:p — paper:Walker2024"
    )


def test_evidence_line_title_defaults_stance_to_supports():
    assert (
        derive_evidence_line_title(
            stance=None, target_id="proposition:p", source="paper:X", evidence_type=None
        )
        == "supports proposition:p — paper:X"
    )


def test_evidence_line_title_head_alone_when_no_tail():
    assert (
        derive_evidence_line_title(
            stance="disputes", target_id="proposition:p", source=None, evidence_type=None
        )
        == "disputes proposition:p"
    )


def test_evidence_line_title_canonicalizes_a_raw_suffixed_token():
    """The create path only ever sees a coerced member; a migration sees raw frontmatter."""
    assert (
        derive_evidence_line_title(
            stance="supports",
            target_id="proposition:p",
            source=None,
            evidence_type="empirical_data_evidence",
        )
        == "supports proposition:p — empirical_data"
    )


def test_evidence_line_title_accepts_an_already_coerced_member():
    assert (
        derive_evidence_line_title(
            stance="supports",
            target_id="proposition:p",
            source=None,
            evidence_type=EvidenceType.EMPIRICAL_DATA,
        )
        == "supports proposition:p — empirical_data"
    )


def test_evidence_line_title_refuses_a_token_that_is_not_a_member():
    """canonical_evidence_type_token does NOT validate membership -- the coercion must."""
    with pytest.raises(ValueError):
        derive_evidence_line_title(
            stance="supports",
            target_id="proposition:p",
            source=None,
            evidence_type="garbage_evidence",
        )
