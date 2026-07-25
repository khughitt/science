from __future__ import annotations

import pytest

from science_model.data_products import build_catalog
from science_model.skill_coverage import EnrollmentStatus, build_skill_overlay
from science_model.skill_coverage.coverage import (
    DatasetUse,
    PlanSkills,
    ProjectEvidence,
    ReportScope,
    SkillCoverageError,
    TermUsage,
    UnresolvedRef,
    compute_coverage,
)

_SCOPE = ReportScope("portfolio")


def _catalog():
    return build_catalog({
        "schema_version": "1",
        "terms": [
            {"id": "data-product:parent", "label": "P", "assay": "a"},
            {"id": "data-product:child-a", "label": "CA", "assay": "a",
             "broader": ["data-product:parent"]},
            {"id": "data-product:child-b", "label": "CB", "assay": "a",
             "broader": ["data-product:parent"]},
            {"id": "data-product:lonely", "label": "L", "assay": "a"},
        ],
    })


def _overlay(catalog):
    # child-a is covered by a measurement-qa leaf; nothing covers child-b/parent/lonely.
    inv = {"skills": [
        {"id": "bio-ca-qa", "name": "bio-ca-qa", "path": "skills/ca.md", "role": "leaf",
         "description": "d", "archetype": "measurement-qa", "covers": ["data-product:child-a"]},
    ]}
    return build_skill_overlay(inv, catalog)


def test_non_enrolled_single_results() -> None:
    catalog = _catalog()
    report = compute_coverage(
        [ProjectEvidence("p1", EnrollmentStatus.OUT_OF_DOMAIN),
         ProjectEvidence("p2", "undeclared")],
        _overlay(catalog), catalog, scope=_SCOPE,
    )
    states = {o.to_dict()["state"] for o in report.coverage_occurrences}
    assert states == {"out-of-domain", "undeclared-domain"}


def test_uncovered_and_candidate_with_sibling_inference() -> None:
    catalog = _catalog()
    overlay = _overlay(catalog)
    # child-b is touched but uncovered; its sibling child-a is covered by a measurement-qa leaf.
    ev = ProjectEvidence(
        "p1", EnrollmentStatus.ENROLLED,
        term_usages=(TermUsage("plan:1", "dataset:x", "data-product:child-b", True),),
    )
    report = compute_coverage([ev], overlay, catalog, scope=_SCOPE)
    unc = [o for o in report.coverage_occurrences if o.to_dict()["state"] == "uncovered"]
    assert len(unc) == 1 and unc[0].term == "data-product:child-b"
    assert len(report.candidates) == 1
    cand = report.candidates[0]
    assert cand.proposed_scope == "data-product:child-b"
    assert cand.score == 0.5
    assert cand.likely_archetype == "measurement-qa"


def test_exact_term_not_ancestor_aware() -> None:
    catalog = _catalog()
    overlay = _overlay(catalog)
    ev = ProjectEvidence(
        "p1", EnrollmentStatus.ENROLLED,
        term_usages=(TermUsage("plan:1", "dataset:x", "data-product:parent", True),),
    )
    report = compute_coverage([ev], overlay, catalog, scope=_SCOPE)
    assert [o.to_dict()["state"] for o in report.coverage_occurrences] == ["uncovered"]


def test_covered_not_loaded_vs_loaded() -> None:
    catalog = _catalog()
    overlay = _overlay(catalog)
    ev = ProjectEvidence(
        "p1", EnrollmentStatus.ENROLLED,
        term_usages=(
            TermUsage("plan:1", "dataset:x", "data-product:child-a", True),
            TermUsage("plan:2", "dataset:x", "data-product:child-a", True),
        ),
        plan_loaded_skills=(PlanSkills("plan:2", ("bio-ca-qa",)),),
    )
    report = compute_coverage([ev], overlay, catalog, scope=_SCOPE)
    cnl = [o for o in report.coverage_occurrences if o.to_dict()["state"] == "covered-not-loaded"]
    assert len(cnl) == 1
    assert cnl[0].available_skill_ids == ("bio-ca-qa",)
    assert {e.plan_ref for e in cnl[0].evidence_refs} == {"plan:1"}


def test_unmapped_and_skill_and_dataset_diagnostics() -> None:
    catalog = _catalog()
    overlay = _overlay(catalog)
    ev = ProjectEvidence(
        "p1", EnrollmentStatus.ENROLLED,
        untagged_usages=(DatasetUse("plan:1", "dataset:untagged"),),
        plan_loaded_skills=(PlanSkills("plan:1", ("ghost-skill",)),),
        unresolved_related_refs=(UnresolvedRef("plan:1", "dataset:gone"),),
    )
    report = compute_coverage([ev], overlay, catalog, scope=_SCOPE)
    assert [o.to_dict()["state"] for o in report.coverage_occurrences] == ["unmapped"]
    assert report.skill_reference_diagnostics[0].skill_id == "ghost-skill"
    assert report.dataset_reference_diagnostics[0].ref == "dataset:gone"


def test_unmapped_groups_and_orders_evidence_by_dataset() -> None:
    catalog = _catalog()
    overlay = _overlay(catalog)
    ev = ProjectEvidence(
        "p1",
        EnrollmentStatus.ENROLLED,
        untagged_usages=(
            DatasetUse("plan:2", "dataset:untagged"),
            DatasetUse("plan:1", "dataset:untagged"),
            DatasetUse("plan:2", "dataset:untagged"),
        ),
    )

    report = compute_coverage([ev], overlay, catalog, scope=_SCOPE)

    unmapped = [
        occurrence
        for occurrence in report.coverage_occurrences
        if occurrence.to_dict()["state"] == "unmapped"
    ]
    assert len(unmapped) == 1
    assert [
        (evidence.plan_ref, evidence.dataset_ref)
        for evidence in unmapped[0].evidence_refs
    ] == [
        ("plan:1", "dataset:untagged"),
        ("plan:2", "dataset:untagged"),
    ]


def test_off_catalog_owned_raises_commons_skips() -> None:
    catalog = _catalog()
    overlay = _overlay(catalog)
    owned = ProjectEvidence("p1", EnrollmentStatus.ENROLLED,
        term_usages=(TermUsage("plan:1", "dataset:x", "data-product:ghost", True),))
    with pytest.raises(SkillCoverageError, match="off-catalog"):
        compute_coverage([owned], overlay, catalog, scope=_SCOPE)
    commons = ProjectEvidence("p1", EnrollmentStatus.ENROLLED,
        term_usages=(TermUsage("plan:1", "dataset:x", "data-product:ghost", False),))
    report = compute_coverage([commons], overlay, catalog, scope=_SCOPE)
    assert report.coverage_occurrences == ()
