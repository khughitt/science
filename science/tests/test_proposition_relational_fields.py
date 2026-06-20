"""Tests for PropositionEntity relational fields (predicate/polarity factored axes)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from science_model.propositions import PropositionEntity


def test_relational_proposition_accepts_factored_axes() -> None:
    p = PropositionEntity(
        id="proposition:p1",
        subject="gene:PHF19",
        predicate="affects",
        object="construct:proliferation",
        polarity="positive",
        claim_layer="causal_effect",
        identification_strength="observational",
        legacy_relation_label="dosage -> transcription",
    )
    assert p.predicate == "affects" and p.polarity == "positive"


def test_signless_predicate_requires_not_applicable_polarity() -> None:
    with pytest.raises(ValidationError):
        PropositionEntity(
            id="proposition:p2",
            subject="gene:A",
            predicate="binds",
            object="gene:B",
            polarity="positive",
            claim_layer="empirical_regularity",
        )


def test_identification_none_and_analogical_are_legal() -> None:
    # model-current contract: none/analogical are valid canonical values
    p = PropositionEntity(
        id="proposition:p3",
        subject="gene:A",
        predicate="affects",
        object="construct:x",
        polarity="unsigned",
        identification_strength="none",
    )
    assert p.identification_strength == "none"


def test_predicate_without_subject_raises() -> None:
    with pytest.raises(ValidationError, match="subject"):
        PropositionEntity(
            id="proposition:p4",
            predicate="affects",
            object="construct:y",
            polarity="positive",
        )


def test_predicate_without_object_raises() -> None:
    with pytest.raises(ValidationError, match="object"):
        PropositionEntity(
            id="proposition:p5",
            predicate="affects",
            subject="gene:A",
            polarity="positive",
        )


def test_sign_meaningful_predicate_not_applicable_polarity_raises() -> None:
    with pytest.raises(ValidationError, match="not_applicable"):
        PropositionEntity(
            id="proposition:p6",
            subject="gene:A",
            predicate="regulates",
            object="gene:B",
            polarity="not_applicable",
        )


def test_signless_predicate_not_applicable_polarity_accepted() -> None:
    p = PropositionEntity(
        id="proposition:p7",
        subject="gene:A",
        predicate="binds",
        object="gene:B",
        polarity="not_applicable",
    )
    assert p.polarity == "not_applicable"


def test_no_predicate_no_subject_object_accepted() -> None:
    # Propositions with no relational fields are valid (legacy/stub propositions).
    p = PropositionEntity(id="proposition:p8")
    assert p.predicate is None
    assert p.subject is None
    assert p.object is None


def test_identification_analogical_is_legal() -> None:
    p = PropositionEntity(
        id="proposition:p9",
        subject="gene:A",
        predicate="affects",
        object="construct:x",
        polarity="positive",
        identification_strength="analogical",
    )
    assert p.identification_strength == "analogical"


def test_sign_meaningful_predicate_requires_explicit_polarity() -> None:
    """sign-meaningful predicate with polarity omitted (None) must raise."""
    with pytest.raises(ValidationError):
        PropositionEntity(id="proposition:p10", subject="gene:A", predicate="affects", object="construct:x")


def test_sign_meaningful_predicate_unsigned_polarity_accepted() -> None:
    """'unsigned' is the correct value for sign-apt but undetermined cases."""
    p = PropositionEntity(
        id="proposition:p11",
        subject="gene:A",
        predicate="affects",
        object="construct:x",
        polarity="unsigned",
    )
    assert p.polarity == "unsigned"
