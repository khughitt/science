from __future__ import annotations

from pathlib import Path

from science_model.audit import ReviewSubmission
from science_model.audit.evidence import LocationEvidence, TextEvidence

from science_tool.findings.reviews import append_review
from science_tool.findings.storage import case_path
from science_tool.validate.checks.review_confirmations import (
    RULE_UNCOUNTED_CONFIRMATION,
    check_review_confirmations,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _ctx(project_root: Path) -> ValidateContext:
    return ValidateContext(
        project_root=project_root,
        doc_dir=project_root / "doc",
        specs_dir=project_root / "entities" / "specs",
        manifest={},
        strict=False,
        verbose=False,
    )


def test_an_unwired_agent_confirmation_is_reported(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation
) -> None:
    unbrokered_run()
    append_review(
        tmp_path,
        stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=agent_attestation(),
    )
    observations = list(check_review_confirmations(_ctx(tmp_path)))
    assert len(observations) == 1
    assert observations[0].severity == Severity.INFO
    assert "NO_EXPOSURE" in observations[0].message
    assert observations[0].path == case_path(tmp_path, stored_case)


def test_a_vacuously_verified_agent_confirmation_is_reported(
    sealed_agent_run, agent_attestation
) -> None:
    """The case revision 26's `review.correspondence-unwired` could not see."""
    project, case, _control = sealed_agent_run
    append_review(
        project,
        case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=agent_attestation(),
    )
    observations = list(check_review_confirmations(_ctx(project)))
    assert len(observations) == 1
    assert "no location evidence" in observations[0].message


def test_a_mixed_evidence_confirmation_is_reported(
    sealed_agent_run, agent_attestation
) -> None:
    project, case, _control = sealed_agent_run
    append_review(
        project,
        case.finding_id,
        ReviewSubmission(
            outcome="confirms",
            note="n",
            evidence=(
                LocationEvidence(type="location", path="science.yaml"),
                TextEvidence(type="text", text="p"),
            ),
        ),
        attestation=agent_attestation(),
    )
    observations = list(check_review_confirmations(_ctx(project)))
    assert len(observations) == 1
    assert "non-location" in observations[0].message


def test_a_counted_agent_confirmation_is_not_reported(
    sealed_agent_run, agent_attestation
) -> None:
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
    assert list(check_review_confirmations(_ctx(project))) == []


def test_human_and_deterministic_reviews_are_not_reported(
    tmp_path: Path, stored_case, human_attestation
) -> None:
    append_review(
        tmp_path,
        stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=human_attestation(),
    )
    append_review(
        tmp_path,
        stored_case.finding_id,
        ReviewSubmission(outcome="confirms", note="n"),
        attestation=human_attestation(
            reviewer_kind="deterministic", reviewer_ref="linter"
        ),
    )
    assert list(check_review_confirmations(_ctx(tmp_path))) == []


def test_a_non_confirming_agent_review_is_not_reported(
    tmp_path: Path, stored_case, unbrokered_run, agent_attestation
) -> None:
    unbrokered_run()
    append_review(
        tmp_path,
        stored_case.finding_id,
        ReviewSubmission(outcome="abstains", note="n"),
        attestation=agent_attestation(),
    )
    assert list(check_review_confirmations(_ctx(tmp_path))) == []


def test_the_finding_keeps_its_rule_and_fingerprint(tmp_path: Path) -> None:
    """Fails if the INFO rule degrades to a bare, unsuppressible notice."""
    from science_tool.validate.findings import is_policy_info_rule

    assert is_policy_info_rule(RULE_UNCOUNTED_CONFIRMATION)


def test_no_cases_yields_nothing(tmp_path: Path) -> None:
    (tmp_path / "doc").mkdir()
    assert list(check_review_confirmations(_ctx(tmp_path))) == []
