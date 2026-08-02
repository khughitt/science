from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from science_model.audit import ReviewSubmission
from science_model.audit.evidence import LocationEvidence

from science_tool.findings.ingest import IngestError
from science_tool.findings.reviews import append_review
from science_tool.findings.storage import load_cases


def test_a_human_review_is_stored_with_no_correspondence(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    attestation = human_attestation()
    review = append_review(
        tmp_path,
        stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="looks right"),
        attestation=attestation,
    )
    assert review.correspondence is None
    assert review.at == attestation.at
    stored = load_cases(tmp_path)[0]
    assert [r.review_id for r in stored.reviews] == [review.review_id]


def test_a_human_review_needs_no_control_plane(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    """No run lookup, no git, no control plane on the non-agent path."""
    assert not (tmp_path / "runs").exists()
    append_review(
        tmp_path,
        stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=human_attestation(),
    )


def test_a_deterministic_review_is_stored(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    review = append_review(
        tmp_path,
        stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=human_attestation(
            reviewer_kind="deterministic", reviewer_ref="linter"
        ),
    )
    assert review.reviewer_kind == "deterministic"


def test_the_stored_at_is_the_attested_instant(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    past = datetime(2020, 1, 1, tzinfo=UTC)
    review = append_review(
        tmp_path,
        stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=human_attestation(at=past),
    )
    assert review.at == past


def test_an_unknown_finding_id_is_refused(
    tmp_path: Path, stored_case, human_attestation, case_files
) -> None:
    before = case_files(tmp_path)
    with pytest.raises(IngestError):
        append_review(
            tmp_path,
            "f" * 64,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=human_attestation(),
        )
    assert case_files(tmp_path) == before


def test_an_unknown_nul_bearing_finding_id_is_an_ingest_error(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    """Derive review_id after the scan so a malformed unknown id stays an IngestError."""
    with pytest.raises(IngestError):
        append_review(
            tmp_path,
            "abc\0def",
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=human_attestation(),
        )


def test_a_duplicate_review_is_refused_and_writes_nothing(
    tmp_path: Path, stored_case, human_attestation, case_files
) -> None:
    submission = ReviewSubmission(outcome="confirms", note="n")
    append_review(
        tmp_path,
        stored_case.finding_id,
        submission,
        attestation=human_attestation(),
    )
    before = case_files(tmp_path)
    with pytest.raises(IngestError, match="already"):
        append_review(
            tmp_path,
            stored_case.finding_id,
            submission,
            attestation=human_attestation(),
        )
    assert case_files(tmp_path) == before


def test_a_forged_submission_raises_ingest_error_not_validation_error(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    """Step 0 recursively rejects a constructed invalid member at the boundary."""
    forged = ReviewSubmission.model_construct(
        outcome="confirms",
        note="n",
        evidence=(
            LocationEvidence.model_construct(
                type="location",
                path="a/../b.txt",
                pointer=None,
                line=None,
                span=None,
            ),
        ),
        uncertainty=(),
    )
    with pytest.raises(IngestError):
        append_review(
            tmp_path,
            stored_case.finding_id,
            forged,
            attestation=human_attestation(),
        )


def test_step_zero_accepts_a_well_formed_pair(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    """Python-mode dumping keeps the attestation datetime valid under strict mode."""
    append_review(
        tmp_path,
        stored_case.finding_id,
        ReviewSubmission(
            outcome="confirms",
            note="n",
            evidence=(LocationEvidence(type="location", path="a.txt"),),
        ),
        attestation=human_attestation(),
    )


def test_a_lock_acquisition_failure_surfaces_as_ingest_error(
    tmp_path: Path,
    stored_case,
    human_attestation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import errno
    import fcntl

    monkeypatch.setattr(
        fcntl,
        "flock",
        lambda fd, op: (_ for _ in ()).throw(OSError(errno.ENOLCK, "no locks")),
    )
    with pytest.raises(IngestError):
        append_review(
            tmp_path,
            stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=human_attestation(),
        )


def test_a_lock_release_failure_surfaces_as_ingest_error(
    tmp_path: Path,
    stored_case,
    human_attestation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import errno
    import fcntl

    real = fcntl.flock

    def flaky(fd: int, op: int) -> None:
        if op == fcntl.LOCK_UN:
            raise OSError(errno.EIO, "release failed")
        real(fd, op)

    monkeypatch.setattr(fcntl, "flock", flaky)
    with pytest.raises(IngestError):
        append_review(
            tmp_path,
            stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=human_attestation(),
        )


def test_a_lock_close_failure_surfaces_as_ingest_error(
    tmp_path: Path,
    stored_case,
    human_attestation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import errno
    import fcntl
    import os

    real_flock = fcntl.flock
    real = os.close
    lock_fd: int | None = None

    def capture_lock(fd: int, op: int) -> None:
        nonlocal lock_fd
        if op == fcntl.LOCK_EX:
            lock_fd = fd
        real_flock(fd, op)

    def flaky(fd: int) -> None:
        nonlocal lock_fd
        if fd == lock_fd:
            lock_fd = None
            raise OSError(errno.EIO, "close failed")
        real(fd)

    monkeypatch.setattr(fcntl, "flock", capture_lock)
    monkeypatch.setattr(os, "close", flaky)
    with pytest.raises(IngestError):
        append_review(
            tmp_path,
            stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=human_attestation(),
        )
