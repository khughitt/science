"""The trusted review-append boundary (design §5.4).

The ONLY function that builds a stored ``Review``. A review's correspondence is
COMPUTED here and cannot be supplied: ``ReviewSubmission`` has no field for it, and the
reviewer's identity comes from a ``ReviewAttestation`` the caller asserts rather than
from anything the producer says about itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError
from science_model.audit import (
    AuditFindingRecord,
    Review,
    ReviewAttestation,
    ReviewSubmission,
    review_id,
)
from science_model.autonomous_runs import RunRecordError

from science_tool.evidence_broker.correspondence import check_correspondence
from science_tool.findings.ingest import IngestError
from science_tool.findings.storage import CaseStorageError, locked_store
from science_tool.graph.autonomous_runs import load_run_records

_Model = TypeVar("_Model", ReviewSubmission, ReviewAttestation)


def _revalidated(value: _Model) -> _Model:
    """Rebuild an argument through its own validators, recursively.

    Passing an instance directly to ``model_validate`` skips members built with
    ``model_construct``. Dumping in Python mode forces recursive validation while
    preserving the attestation's datetime for strict validation.
    """
    try:
        dumped = value.model_dump(mode="python", warnings="error")
        return type(value).model_validate(dumped, strict=True)
    except (ValidationError, ValueError, TypeError) as exc:
        raise IngestError(f"{type(value).__name__} is not valid: {exc}") from exc


def append_review(
    project_root: Path,
    finding_id: str,
    submission: ReviewSubmission,
    *,
    attestation: ReviewAttestation,
) -> Review:
    """Append one review to a stored case, computing its correspondence."""
    # Step 0: revalidate both arguments before reading either.
    submission = _revalidated(submission)
    attestation = _revalidated(attestation)

    if attestation.reviewer_kind != "agent":
        correspondence = None
    else:
        try:
            records = load_run_records(project_root)
        except (RunRecordError, OSError) as exc:
            # BOTH: `Path.exists()` swallows only the not-found family and `iterdir()`
            # swallows nothing, so an unreadable runs/ arrives as a raw OSError from a
            # function whose documented channel is RunRecordError.
            raise IngestError(f"could not resolve {attestation.run_ref!r}: {exc}") from exc
        run = next((r for r in records if r.id == attestation.run_ref), None)
        if run is None:
            # NOT a stored `unwired`: with no record, neither cross-check can run and no
            # sealed exposure provenance exists, so the stored review's run_ref would
            # point at nothing. §6 already calls the lost-journal branch retryable.
            raise IngestError(f"no run record has id {attestation.run_ref!r}")

        # The cross-checks run BEFORE the checker: they refuse, so there is no reason to
        # replay git for a review that will be rejected.
        if attestation.reviewer_ref != run.agent:
            raise IngestError(
                f"attested reviewer_ref {attestation.reviewer_ref!r} is not the run's "
                f"agent {run.agent!r}"
            )
        if attestation.model != run.model:
            raise IngestError(
                f"attested model {attestation.model!r} is not the run's model {run.model!r}"
            )
        # Conditional: an unbrokered run has no instrument, and §5.3 requires exactly
        # that case be stored as `unwired`.
        if run.evidence is not None and attestation.lens != run.evidence.instrument.ref:
            raise IngestError(
                f"attested lens {attestation.lens!r} is not the exposure's instrument "
                f"{run.evidence.instrument.ref!r}"
            )

        correspondence = check_correspondence(
            submission.evidence, run.evidence, repo=project_root
        )
        if correspondence.status == "violated":
            raise IngestError(
                "review does not correspond to what the run was shown: "
                f"{correspondence.code} — {correspondence.reason}"
            )

    try:
        with locked_store(project_root) as store:
            # Scan through the held descriptor; CaseStore has no load-by-id API.
            record: AuditFindingRecord | None = None
            for name in store.names():
                candidate = store.read(name)
                if candidate.finding_id == finding_id:
                    record = candidate
                    break
            if record is None:
                raise IngestError(f"no stored case has finding_id {finding_id!r}")

            # Derive only after a match so malformed unknown ids remain IngestError.
            identity = review_id(
                reviewer_kind=attestation.reviewer_kind,
                reviewer_ref=attestation.reviewer_ref,
                lens=attestation.lens,
                run_ref=attestation.run_ref,
                finding_id=record.finding_id,
            )
            if any(existing.review_id == identity for existing in record.reviews):
                raise IngestError(f"review {identity!r} is already stored on this case")

            review = Review(
                review_id=identity,
                reviewer_kind=attestation.reviewer_kind,
                reviewer_ref=attestation.reviewer_ref,
                lens=attestation.lens,
                model=attestation.model,
                run_ref=attestation.run_ref,
                at=attestation.at,
                outcome=submission.outcome,
                note=submission.note,
                evidence=submission.evidence,
                uncertainty=submission.uncertainty,
                correspondence=correspondence,
            )
            store.write(record.with_review(review))
            return review
    except CaseStorageError as exc:
        raise IngestError(str(exc)) from exc
