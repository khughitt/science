from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from science_model.audit import (
    Review,
    ReviewAttestation,
    ReviewSubmission,
    Uncertainty,
    review_id,
)
from science_model.audit.evidence import (
    MAX_EVIDENCE_ENTRIES,
    LocationEvidence,
    TextEvidence,
)
from science_model.audit.record import MAX_UNCERTAINTY_ENTRIES
from science_model.correspondence import Correspondence

AT = datetime(2026, 8, 2, tzinfo=UTC)
FINDING_ID = "0" * 64


def _attestation(**overrides: object) -> ReviewAttestation:
    fields: dict[str, object] = {
        "reviewer_kind": "agent",
        "reviewer_ref": "curation-sweep",
        "lens": "instrument:review-v1",
        "model": "test-model",
        "run_ref": "run:2026-08-02-curation-sweep-a3f1",
        "at": AT,
    }
    fields.update(overrides)
    return ReviewAttestation(**fields)  # type: ignore[arg-type]


def _review(**overrides: object) -> Review:
    fields: dict[str, object] = {
        "reviewer_kind": "agent",
        "reviewer_ref": "curation-sweep",
        "lens": "instrument:review-v1",
        "model": "test-model",
        "run_ref": "run:2026-08-02-curation-sweep-a3f1",
        "at": AT,
        "outcome": "confirms",
        "note": "n",
        "correspondence": Correspondence(status="verified"),
    }
    fields.update(overrides)
    fields["review_id"] = review_id(
        reviewer_kind=fields["reviewer_kind"],  # type: ignore[arg-type]
        reviewer_ref=fields["reviewer_ref"],  # type: ignore[arg-type]
        lens=fields["lens"],  # type: ignore[arg-type]
        run_ref=fields["run_ref"],  # type: ignore[arg-type]
        finding_id=FINDING_ID,
    )
    return Review(**fields)  # type: ignore[arg-type]


def test_max_uncertainty_entries_is_the_evidence_bound() -> None:
    assert MAX_UNCERTAINTY_ENTRIES == MAX_EVIDENCE_ENTRIES


def test_submission_cannot_express_a_reviewer_kind() -> None:
    with pytest.raises(ValidationError):
        ReviewSubmission(outcome="confirms", note="n", reviewer_kind="human")  # type: ignore[call-arg]


def test_submission_cannot_express_a_correspondence() -> None:
    with pytest.raises(ValidationError):
        ReviewSubmission(outcome="confirms", note="n", correspondence={"status": "verified"})  # type: ignore[call-arg]


def test_submission_bounds_evidence() -> None:
    entry = TextEvidence(type="text", text="x")
    ReviewSubmission(outcome="confirms", note="n", evidence=(entry,) * MAX_EVIDENCE_ENTRIES)
    with pytest.raises(ValidationError):
        ReviewSubmission(
            outcome="confirms", note="n", evidence=(entry,) * (MAX_EVIDENCE_ENTRIES + 1)
        )


def test_submission_bounds_uncertainty() -> None:
    item = Uncertainty(field="severity", what="unsure", why="thin evidence")
    ReviewSubmission(outcome="confirms", note="n", uncertainty=(item,) * MAX_UNCERTAINTY_ENTRIES)
    with pytest.raises(ValidationError):
        ReviewSubmission(
            outcome="confirms", note="n", uncertainty=(item,) * (MAX_UNCERTAINTY_ENTRIES + 1)
        )


def test_agent_attestation_requires_a_lens() -> None:
    with pytest.raises(ValidationError, match="lens"):
        _attestation(lens=None)


def test_agent_attestation_requires_a_model() -> None:
    """`lens` present, so this can only fail on `model`."""
    with pytest.raises(ValidationError, match="model"):
        _attestation(model=None)


def test_non_agent_attestation_needs_neither() -> None:
    assert _attestation(reviewer_kind="human", lens=None, model=None).lens is None
    assert _attestation(reviewer_kind="deterministic", lens=None, model=None).model is None


def test_uncertainty_rejects_a_blank_field() -> None:
    with pytest.raises(ValidationError):
        Uncertainty(field="  ", what="unsure", why="thin evidence")


def test_agent_review_requires_a_correspondence() -> None:
    with pytest.raises(ValidationError, match="correspondence"):
        _review(correspondence=None)


def test_non_agent_review_needs_no_correspondence() -> None:
    assert _review(reviewer_kind="human", lens=None, model=None, correspondence=None).correspondence is None


def test_violated_is_unstorable() -> None:
    with pytest.raises(ValidationError, match="violated"):
        _review(correspondence=Correspondence(status="violated", code="CITATION_UNSERVED"))


def test_unwired_is_storable() -> None:
    stored = _review(correspondence=Correspondence(status="unwired", code="NO_EXPOSURE"))
    assert stored.correspondence is not None
    assert stored.correspondence.status == "unwired"


def test_review_bounds_evidence() -> None:
    entry = LocationEvidence(type="location", path="a.txt")
    _review(evidence=(entry,) * MAX_EVIDENCE_ENTRIES)
    with pytest.raises(ValidationError):
        _review(evidence=(entry,) * (MAX_EVIDENCE_ENTRIES + 1))


def test_review_bounds_uncertainty() -> None:
    item = Uncertainty(field="severity", what="unsure", why="thin evidence")
    _review(uncertainty=(item,) * MAX_UNCERTAINTY_ENTRIES)
    with pytest.raises(ValidationError):
        _review(uncertainty=(item,) * (MAX_UNCERTAINTY_ENTRIES + 1))


def test_a_forged_nested_correspondence_is_refused() -> None:
    """Measured behaviour, asserted so it cannot regress silently.

    `Review` inherits `_Base.revalidate_instances="always"`, so a Correspondence
    built past its own validator is re-validated when the Review is constructed.
    """
    forged = Correspondence.model_construct(status="verified", code="SHOULD_BE_FORBIDDEN")
    with pytest.raises(ValidationError):
        _review(correspondence=forged)
