from __future__ import annotations

import json

import pytest

from science_model.skill_coverage import EnrollmentStatus
from science_model.skill_coverage.coverage import (
    Candidate,
    CoverageReport,
    CoveredNotLoadedOccurrence,
    DatasetReferenceDiagnostic,
    EvidencePair,
    EvidenceTriple,
    OutOfDomainResult,
    ProjectEvidence,
    ReportScope,
    SkillCoverageError,
    SkillReferenceDiagnostic,
    SkippedProject,
    TermUsage,
    UncoveredOccurrence,
    UndeclaredDomainResult,
    UnmappedOccurrence,
    serialize_coverage_report,
)


def test_project_evidence_rejects_facts_when_not_enrolled() -> None:
    with pytest.raises(SkillCoverageError, match="non-enrolled"):
        ProjectEvidence(
            project="p",
            enrollment="undeclared",
            term_usages=(TermUsage("plan:1", "dataset:x", "data-product:t", True),),
        )
    # enrolled with facts is fine; non-enrolled with no facts is fine
    ProjectEvidence(
        project="p", enrollment=EnrollmentStatus.ENROLLED, untagged_usages=()
    )
    ProjectEvidence(project="p", enrollment=EnrollmentStatus.OUT_OF_DOMAIN)


def test_occurrence_to_dict_shapes() -> None:
    assert OutOfDomainResult("p").to_dict() == {
        "state": "out-of-domain",
        "project": "p",
    }
    assert UndeclaredDomainResult("p").to_dict() == {
        "state": "undeclared-domain",
        "project": "p",
    }
    um = UnmappedOccurrence(
        "p", "dataset:x", (EvidencePair("plan:1", "dataset:x"),)
    )
    assert um.to_dict() == {
        "state": "unmapped",
        "project": "p",
        "dataset_ref": "dataset:x",
        "observation_level": "analysis-usage",
        "evidence_refs": [{"plan_ref": "plan:1", "dataset_ref": "dataset:x"}],
    }
    cnl = CoveredNotLoadedOccurrence(
        "p",
        "data-product:t",
        ("bio-x",),
        (EvidencePair("plan:1", "dataset:x"),),
    )
    assert cnl.to_dict()["available_skill_ids"] == ["bio-x"]
    assert cnl.to_dict()["state"] == "covered-not-loaded"


def test_report_orders_deterministically_including_tying_unmapped() -> None:
    # Two unmapped entries in one project tie on (state, project, "") and must fall
    # through to the scalar evidence-pair key without raising (the list-of-dicts guard).
    report = CoverageReport(
        scope=ReportScope("portfolio"),
        coverage_occurrences=(
            UnmappedOccurrence(
                "p", "dataset:b", (EvidencePair("plan:2", "dataset:b"),)
            ),
            UnmappedOccurrence(
                "p", "dataset:a", (EvidencePair("plan:1", "dataset:a"),)
            ),
            UncoveredOccurrence(
                "p", "data-product:t", (EvidencePair("plan:1", "dataset:a"),)
            ),
        ),
        skill_reference_diagnostics=(
            SkillReferenceDiagnostic("p", "plan:9", "ghost"),
        ),
        dataset_reference_diagnostics=(
            DatasetReferenceDiagnostic("p", "plan:9", "dataset:gone"),
        ),
        candidates=(
            Candidate(
                "data-product:t",
                "indeterminate",
                0.5,
                (EvidenceTriple("p", "plan:1", "dataset:a"),),
            ),
        ),
        skipped_projects=(
            SkippedProject("/x/stale", "path missing or no science.yaml"),
        ),
    )
    text = serialize_coverage_report(report)
    assert text.endswith("\n")
    obj = json.loads(text)
    # unmapped entries sorted by their (plan_ref, dataset_ref) pair key
    unmapped = [
        occurrence
        for occurrence in obj["coverage_occurrences"]
        if occurrence["state"] == "unmapped"
    ]
    assert [occurrence["dataset_ref"] for occurrence in unmapped] == [
        "dataset:a",
        "dataset:b",
    ]
    assert obj["scope"] == {"mode": "portfolio"}
    assert obj["skipped_projects"] == [
        {"path": "/x/stale", "reason": "path missing or no science.yaml"}
    ]
    assert serialize_coverage_report(report) == text  # deterministic


def test_scope_single_project_carries_project() -> None:
    assert ReportScope("single-project", "mm30").to_dict() == {
        "mode": "single-project",
        "project": "mm30",
    }
