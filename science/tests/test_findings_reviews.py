from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from science_model.audit import ReviewAttestation, ReviewSubmission
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


def test_an_agent_review_of_an_unbrokered_run_is_unwired(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation
) -> None:
    unbrokered_run()
    review = append_review(
        tmp_path,
        stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=agent_attestation(),
    )
    assert review.correspondence is not None
    assert review.correspondence.status == "unwired"
    assert review.correspondence.code == "NO_EXPOSURE"


def test_the_lens_check_is_skipped_when_the_run_has_no_exposure(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation
) -> None:
    unbrokered_run()
    review = append_review(
        tmp_path,
        stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=agent_attestation(lens="something-else.md"),
    )
    assert review.correspondence is not None
    assert review.correspondence.status == "unwired"


def test_a_lens_mismatch_against_an_EXPOSED_run_is_refused(
    sealed_agent_run, agent_attestation
) -> None:
    """Exercise the lens comparison against a run that actually has an exposure."""
    project, case, _control = sealed_agent_run
    with pytest.raises(IngestError, match="lens|instrument"):
        append_review(
            project,
            case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=agent_attestation(lens="not-the-instrument.md"),
        )


def test_a_reviewer_ref_mismatch_is_refused(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation
) -> None:
    """`model` agrees, so this can only fail on reviewer_ref."""
    unbrokered_run(agent="curation-sweep", model="test-model")
    with pytest.raises(IngestError, match="reviewer_ref|agent"):
        append_review(
            tmp_path,
            stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=agent_attestation(reviewer_ref="someone-else", model="test-model"),
        )


def test_a_model_mismatch_is_refused(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation
) -> None:
    """`reviewer_ref` agrees, so this can only fail on model."""
    unbrokered_run(agent="curation-sweep", model="test-model")
    with pytest.raises(IngestError, match="model"):
        append_review(
            tmp_path,
            stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=agent_attestation(
                reviewer_ref="curation-sweep", model="a-different-model"
            ),
        )


def test_a_run_ref_with_no_record_is_refused_and_writes_nothing(
    tmp_path: Path, stored_case, agent_attestation, case_files
) -> None:
    before = case_files(tmp_path)
    with pytest.raises(IngestError):
        append_review(
            tmp_path,
            stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=agent_attestation(run_ref="run:2020-01-01-nobody-0000"),
        )
    assert case_files(tmp_path) == before


def test_a_symlinked_runs_directory_is_refused(
    tmp_path: Path, stored_case, agent_attestation
) -> None:
    elsewhere = tmp_path.parent / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "runs").symlink_to(elsewhere)
    with pytest.raises(IngestError):
        append_review(
            tmp_path,
            stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=agent_attestation(),
        )


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unreadable_runs_directory_is_an_ingest_error(
    tmp_path: Path, stored_case, agent_attestation
) -> None:
    """A raw OSError from `load_run_records` stays inside the IngestError boundary."""
    runs = tmp_path / "runs"
    runs.mkdir()
    runs.chmod(0o000)
    try:
        with pytest.raises(IngestError):
            append_review(
                tmp_path,
                stored_case.finding_id,
                ReviewSubmission(outcome="confirms", note="n"),
                attestation=agent_attestation(),
            )
    finally:
        runs.chmod(0o755)


def test_a_forged_attestation_is_refused_before_the_run_lookup(
    tmp_path: Path, stored_case, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The load-bearing assertion is that recursive validation prevents run lookup."""
    monkeypatch.setattr(
        "science_tool.findings.reviews.load_run_records",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("run lookup ran")),
    )
    forged = ReviewAttestation.model_construct(
        reviewer_kind="agent",
        reviewer_ref="curation-sweep",
        lens=None,
        model="test-model",
        run_ref="run:2026-07-25-curation-sweep-a3f1",
        at=datetime(2026, 8, 2, tzinfo=UTC),
    )
    with pytest.raises(IngestError):
        append_review(
            tmp_path,
            stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=forged,
        )


def test_a_forged_submission_is_refused_before_the_checker(
    tmp_path: Path,
    stored_case,
    unbrokered_run,
    agent_attestation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The agent path recursively validates the submission before correspondence."""
    unbrokered_run()
    monkeypatch.setattr(
        "science_tool.findings.reviews.check_correspondence",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("checker ran")),
    )
    forged = ReviewSubmission.model_construct(
        outcome="confirms",
        note="n",
        evidence=(
            LocationEvidence.model_construct(
                type="location", path="a/../b.txt", pointer=None, line=None, span=None
            ),
        ),
        uncertainty=(),
    )
    with pytest.raises(IngestError):
        append_review(
            tmp_path,
            stored_case.finding_id,
            forged,
            attestation=agent_attestation(),
        )


def test_the_cross_checks_run_before_the_checker(
    tmp_path: Path,
    stored_case,
    unbrokered_run,
    agent_attestation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refusing identity cross-check must run before correspondence replay."""
    from science_tool.evidence_broker.serve import ServeError

    unbrokered_run(agent="curation-sweep", model="test-model")
    monkeypatch.setattr(
        "science_tool.findings.reviews.check_correspondence",
        lambda *a, **k: (_ for _ in ()).throw(ServeError("replay exploded")),
    )
    with pytest.raises(IngestError, match="model"):
        append_review(
            tmp_path,
            stored_case.finding_id,
            ReviewSubmission(outcome="confirms", note="n"),
            attestation=agent_attestation(model="a-different-model"),
        )


def test_a_sealed_run_replays_with_the_control_plane_deleted(
    sealed_agent_run, agent_attestation
) -> None:
    """`append_review` resolves the sealed run record and no live baseline state."""
    import shutil

    project, case, control_plane_dir = sealed_agent_run
    shutil.rmtree(control_plane_dir)
    review = append_review(
        project,
        case.finding_id,
        ReviewSubmission(
            outcome="confirms",
            note="n",
            evidence=(LocationEvidence(type="location", path="science.yaml"),),
        ),
        attestation=agent_attestation(),
    )
    assert review.correspondence is not None
    assert review.correspondence.status == "verified"


def test_a_citation_the_run_was_never_shown_is_refused(
    sealed_agent_run, agent_attestation, case_files
) -> None:
    project, case, _control = sealed_agent_run
    before = case_files(project)
    with pytest.raises(IngestError, match="CITATION_UNSERVED"):
        append_review(
            project,
            case.finding_id,
            ReviewSubmission(
                outcome="confirms",
                note="n",
                evidence=(LocationEvidence(type="location", path="never-read.txt"),),
            ),
            attestation=agent_attestation(),
        )
    assert case_files(project) == before


def test_a_verified_agent_confirmation_counts(
    sealed_agent_run, agent_attestation
) -> None:
    """End-to-end: a verified agent confirmation affects the stored case."""
    project, case, _control = sealed_agent_run
    append_review(
        project,
        case.finding_id,
        ReviewSubmission(
            outcome="confirms",
            note="n",
            evidence=(LocationEvidence(type="location", path="science.yaml"),),
        ),
        attestation=agent_attestation(),
    )
    assert load_cases(project)[0].confirmation_count() == 1
