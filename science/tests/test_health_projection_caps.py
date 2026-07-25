from __future__ import annotations

import pytest

from science_tool.graph.health import count_issues
from science_tool.graph.health_projection import (
    SECTION_ROW_CAP,
    UnknownSection,
    project_health_report,
)


def _natural_systems_shaped_report() -> dict[str, object]:
    """All-warning validation against a non-zero total_issues -- the real 2026-07-24 shape."""
    return {
        "validation": [
            {"severity": "warning", "code": "document_structure", "message": f"m{i}"}
            for i in range(361)
        ],
        "managed_artifacts": [{"counts_as_issue": False, "name": "a"}],
        "unresolved_refs": [{"ref": "r1"}, {"ref": "r2"}],
        "unregistered_ref_kinds": [],
        "lingering_tags_lines": [],
        "agent_context": [],
        "identity_policy": [],
        "entity_identity": [],
        "legacy_task_type": [],
        "invalid_entity_aspects": [],
        "dataset_anomalies": [],
        "schema_invalid": [],
        "tooling_scaffold": [],
        "accepted_validation": [],
        "archive_lag": {"done_in_active": 4, "retired_in_active": 0, "missing_completed": 1},
        "unwired_checks": [],
        "layered_claims": {
            "proposition_claim_layer_coverage": {
                "numerator": 0,
                "denominator": 0,
                "fraction": 1.0,
            },
            "causal_leaning_identification_coverage": {
                "numerator": 0,
                "denominator": 0,
                "fraction": 1.0,
            },
            "rival_model_packets_missing_discriminating_predictions": [],
            "migration_issues": [],
        },
        "cross_paper_evidence": {
            "status": "ok",
            "empty_state": "no_propositions",
            "summary": {},
            "findings": [],
            "propositions": [],
        },
        "prose_epistemics": {
            "applicable": False,
            "summary": {},
            "coverage": {},
            "sources": [],
            "findings": [],
        },
        "total_issues": 364,
    }


def test_default_warn_threshold_does_not_empty_an_all_warning_report() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert len(projected["validation"]) == SECTION_ROW_CAP


def test_section_omitted_records_what_was_dropped() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert projected["section_omitted"]["validation"] == 361 - SECTION_ROW_CAP


def test_total_issues_is_never_rewritten() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert projected["total_issues"] == 364


def test_displayed_issues_uses_the_same_counting_rules_as_total() -> None:
    """displayed_issues must be count_issues(projected), not a raw row count.

    The fixture's single managed_artifacts row has counts_as_issue=False, so it must NOT
    contribute; unresolved_refs and archive_lag must.
    """
    report = _natural_systems_shaped_report()
    projected = project_health_report(report, threshold="warn")
    assert projected["displayed_issues"] == count_issues(projected)
    # 40 validation + 2 unresolved_refs + 1 archive_lag; managed_artifacts excluded.
    assert projected["displayed_issues"] == SECTION_ROW_CAP + 3


def test_displayed_never_exceeds_total() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert projected["displayed_issues"] <= projected["total_issues"]


def test_error_threshold_hides_warnings_but_reports_them_as_omitted() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="error")
    assert projected["validation"] == []
    assert projected["section_omitted"]["validation"] == 361
    assert projected["total_issues"] == 364


def test_unfiltered_sections_ignore_threshold_and_cap() -> None:
    report = _natural_systems_shaped_report()
    report["unwired_checks"] = [{"name": f"check{i}"} for i in range(100)]
    projected = project_health_report(report, threshold="error")
    assert len(projected["unwired_checks"]) == 100


def test_counts_as_issue_section_is_not_severity_filtered() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="error")
    assert len(projected["managed_artifacts"]) == 1


def test_nested_findings_are_projected_in_place() -> None:
    report = _natural_systems_shaped_report()
    report["cross_paper_evidence"] = {
        "status": "active",
        "empty_state": "active",
        "summary": {},
        "findings": [{"severity": "error", "code": f"c{i}"} for i in range(100)],
        "propositions": [],
    }
    projected = project_health_report(report, threshold="error")
    assert len(projected["cross_paper_evidence"]["findings"]) == SECTION_ROW_CAP
    assert projected["cross_paper_evidence"]["status"] == "active"


@pytest.mark.parametrize(
    ("section", "value"),
    [("validation", {}), ("managed_artifacts", "findings"), ("unresolved_refs", None)],
)
def test_registered_row_sections_reject_non_lists(section: str, value: object) -> None:
    report = _natural_systems_shaped_report()
    report[section] = value
    with pytest.raises(TypeError, match=section):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize(
    "section",
    ["validation", "managed_artifacts", "unresolved_refs"],
)
def test_registered_row_sections_reject_non_mapping_members(section: str) -> None:
    report = _natural_systems_shaped_report()
    report[section] = [None]
    with pytest.raises(TypeError, match=rf"{section}\[0\]"):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("cross_paper_evidence", {}),
        ("cross_paper_evidence", {"findings": {}}),
        (
            "cross_paper_evidence",
            {
                "status": "ok",
                "empty_state": "active",
                "summary": [],
                "findings": [],
                "propositions": [],
            },
        ),
        (
            "cross_paper_evidence",
            {
                "status": "ok",
                "empty_state": "active",
                "summary": {},
                "findings": [],
            },
        ),
        ("prose_epistemics", {}),
        ("prose_epistemics", {"findings": None}),
        (
            "prose_epistemics",
            {
                "applicable": "no",
                "summary": {},
                "coverage": {},
                "sources": [],
                "findings": [],
            },
        ),
        (
            "prose_epistemics",
            {
                "applicable": False,
                "summary": {},
                "coverage": {},
                "findings": [],
            },
        ),
    ],
)
def test_nested_sections_require_their_registered_shape(
    section: str, value: object
) -> None:
    report = _natural_systems_shaped_report()
    report[section] = value
    with pytest.raises((TypeError, ValueError), match=section):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize("section", ["archive_lag", "layered_claims"])
def test_registered_mapping_sections_reject_non_mappings(section: str) -> None:
    report = _natural_systems_shaped_report()
    report[section] = []
    with pytest.raises(TypeError, match=section):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("archive_lag", {"done_in_active": 0, "retired_in_active": 0}),
        (
            "archive_lag",
            {"done_in_active": "zero", "retired_in_active": 0, "missing_completed": 0},
        ),
        (
            "layered_claims",
            {
                "proposition_claim_layer_coverage": {
                    "numerator": 0,
                    "denominator": 0,
                    "fraction": 1.0,
                },
                "causal_leaning_identification_coverage": {
                    "numerator": 0,
                    "denominator": 0,
                    "fraction": 1.0,
                },
                "migration_issues": [],
            },
        ),
        (
            "layered_claims",
            {
                "proposition_claim_layer_coverage": {
                    "numerator": 0,
                    "denominator": 0,
                    "fraction": 1.0,
                },
                "causal_leaning_identification_coverage": {
                    "numerator": 0,
                    "denominator": "zero",
                    "fraction": 1.0,
                },
                "rival_model_packets_missing_discriminating_predictions": [],
                "migration_issues": [],
            },
        ),
    ],
)
def test_mapping_sections_require_their_registered_shape(
    section: str, value: object
) -> None:
    report = _natural_systems_shaped_report()
    report[section] = value
    with pytest.raises((TypeError, ValueError), match=section):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize("section", ["cross_paper_evidence", "prose_epistemics"])
def test_nested_findings_reject_non_mapping_members(section: str) -> None:
    report = _natural_systems_shaped_report()
    nested = dict(report[section])
    nested["findings"] = [None]
    report[section] = nested
    with pytest.raises(TypeError, match=rf"{section}\.findings\[0\]"):
        project_health_report(report, threshold="warn")


def test_unknown_list_section_refuses_rather_than_capping() -> None:
    report = _natural_systems_shaped_report()
    report["brand_new_check"] = [{"severity": "error"}] * 500
    with pytest.raises(UnknownSection, match="brand_new_check"):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize("value", [True, 7, "clean", 1.5, None])
def test_unknown_scalar_section_refuses(value: object) -> None:
    """A new scalar section must be classified too.

    A type test (`not isinstance(value, (list, dict))`) would wave every one of these
    through unexamined -- a new `"degraded": True` or `"entity_count": 41000` would join
    the report with nobody having decided what it means for the budget.
    """
    report = _natural_systems_shaped_report()
    report["brand_new_scalar"] = value
    with pytest.raises(UnknownSection, match="brand_new_scalar"):
        project_health_report(report, threshold="warn")


def test_registered_scalars_still_pass_through() -> None:
    report = _natural_systems_shaped_report()
    report["_meta"] = {"timings": [], "total_duration_seconds": 0.5}
    projected = project_health_report(report, threshold="warn")
    assert projected["_meta"] == {"timings": [], "total_duration_seconds": 0.5}
    assert projected["total_issues"] == report["total_issues"]


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("total_issues", "364"),
        ("_meta", {"timings": []}),
        ("_meta", {"timings": {}, "total_duration_seconds": 0.5}),
    ],
)
def test_registered_scalars_require_their_registered_shape(
    section: str, value: object
) -> None:
    report = _natural_systems_shaped_report()
    report[section] = value
    with pytest.raises((TypeError, ValueError), match=section):
        project_health_report(report, threshold="warn")
