from __future__ import annotations

import pytest

from science_tool.graph.health_count import count_issues
from science_tool.graph.health_projection import (
    SECTION_ROW_CAP,
    UnknownSection,
    project_health_report,
)


def _natural_systems_shaped_report() -> dict[str, object]:
    """All-warning validation against a non-zero total_issues -- the real 2026-07-24 shape."""
    return {
        "validation": [
            {
                "severity": "warning",
                "path": None,
                "line": None,
                "message": f"m{i}",
                "rule": "document_structure",
                "task": None,
            }
            for i in range(361)
        ],
        "managed_artifacts": [
            {
                "name": "a",
                "install_target": "AGENTS.md",
                "version": "1",
                "status": "current",
                "detail": "current",
                "counts_as_issue": False,
            }
        ],
        "unresolved_refs": [
            {
                "target": "r1",
                "mention_count": 1,
                "sources": ["a.md"],
                "looks_like": "unknown",
            },
            {
                "target": "r2",
                "mention_count": 1,
                "sources": ["b.md"],
                "looks_like": "unknown",
            },
        ],
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
        "total_issues": 363,
    }


def test_default_warn_threshold_does_not_empty_an_all_warning_report() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert len(projected["validation"]) == SECTION_ROW_CAP


def test_section_omitted_records_what_was_dropped() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert projected["section_omitted"]["validation"] == 361 - SECTION_ROW_CAP


def test_total_issues_is_never_rewritten() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert projected["total_issues"] == 363


def test_displayed_issues_uses_the_same_counting_rules_as_total() -> None:
    """displayed_issues must be count_issues(projected), not a raw row count.

    The fixture's single managed_artifacts row has counts_as_issue=False, so it must NOT
    contribute; unresolved_refs must.
    """
    report = _natural_systems_shaped_report()
    projected = project_health_report(report, threshold="warn")
    assert projected["displayed_issues"] == count_issues(projected)
    # 40 validation + 2 unresolved_refs; managed_artifacts excluded.
    assert projected["displayed_issues"] == SECTION_ROW_CAP + 2


def test_displayed_never_exceeds_total() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="warn")
    assert projected["displayed_issues"] <= projected["total_issues"]


def test_error_threshold_hides_warnings_but_reports_them_as_omitted() -> None:
    projected = project_health_report(_natural_systems_shaped_report(), threshold="error")
    assert projected["validation"] == []
    assert projected["section_omitted"]["validation"] == 361
    assert projected["total_issues"] == 363


def test_unfiltered_sections_ignore_threshold_and_cap() -> None:
    report = _natural_systems_shaped_report()
    report["unwired_checks"] = [
        {"check": f"check{i}", "code": "unwired", "reason": None} for i in range(100)
    ]
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
        "findings": [
            {
                "severity": "error",
                "code": f"c{i}",
                "sidecar": "annotations/a.json",
                "annotation": "annotation:a",
                "reason": "invalid",
                "detail": "invalid annotation",
            }
            for i in range(100)
        ],
        "propositions": [],
    }
    report["total_issues"] = 463
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


def test_registered_mapping_sections_reject_non_mappings() -> None:
    report = _natural_systems_shaped_report()
    report["layered_claims"] = []
    with pytest.raises(TypeError, match="layered_claims"):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize(
    ("section", "value"),
    [
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
        ("total_issues", "363"),
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


@pytest.mark.parametrize("cap", [-1, True, False, 1.5, "40"])
def test_cap_must_be_a_non_negative_integer(cap: object) -> None:
    with pytest.raises((TypeError, ValueError), match="cap"):
        project_health_report(_natural_systems_shaped_report(), threshold="warn", cap=cap)


def test_zero_cap_is_valid() -> None:
    projected = project_health_report(
        _natural_systems_shaped_report(), threshold="warn", cap=0
    )
    assert projected["validation"] == []


def test_projector_rejects_unknown_threshold_when_severity_sections_are_empty() -> None:
    report = _natural_systems_shaped_report()
    report["validation"] = []
    with pytest.raises(ValueError, match="unknown health threshold"):
        project_health_report(report, threshold="critical")


@pytest.mark.parametrize(
    "section",
    [
        "unresolved_refs",
        "unregistered_ref_kinds",
        "lingering_tags_lines",
        "agent_context",
        "identity_policy",
        "entity_identity",
        "legacy_task_type",
        "invalid_entity_aspects",
        "schema_invalid",
        "managed_artifacts",
        "tooling_scaffold",
        "validation",
        "accepted_validation",
        "unwired_checks",
    ],
)
def test_typed_dict_row_sections_require_their_producer_fields(section: str) -> None:
    report = _natural_systems_shaped_report()
    report[section] = [{}]
    with pytest.raises((TypeError, ValueError), match=rf"{section}\[0\]"):
        project_health_report(report, threshold="warn")


def test_malformed_typed_row_beyond_cap_is_rejected_before_projection() -> None:
    report = _natural_systems_shaped_report()
    rows = list(report["validation"])
    rows[SECTION_ROW_CAP].pop("message")
    report["validation"] = rows
    with pytest.raises(ValueError, match=rf"validation\[{SECTION_ROW_CAP}\].*message"):
        project_health_report(report, threshold="warn")


def test_malformed_managed_artifact_beyond_cap_is_rejected_before_projection() -> None:
    report = _natural_systems_shaped_report()
    valid = dict(report["managed_artifacts"][0])
    report["managed_artifacts"] = [
        dict(valid) for _ in range(SECTION_ROW_CAP)
    ] + [{**valid, "counts_as_issue": "yes"}]
    with pytest.raises(
        TypeError,
        match=rf"managed_artifacts\[{SECTION_ROW_CAP}\]\.counts_as_issue",
    ):
        project_health_report(report, threshold="warn")


def test_filtered_prose_finding_is_validated_before_thresholding() -> None:
    report = _natural_systems_shaped_report()
    prose = dict(report["prose_epistemics"])
    prose["findings"] = [
        {
            "code": "undeclared_grounding_report",
            "severity": "info",
            "source_ref": "prose-source:a",
            "path": "data/prose-grounding/a/grounding.json",
            "message": "undeclared report",
        }
    ]
    report["prose_epistemics"] = prose
    with pytest.raises(ValueError, match=r"prose_epistemics\.findings\[0\].*counts_as_issue"):
        project_health_report(report, threshold="warn")


def test_cross_paper_finding_requires_full_producer_shape_before_capping() -> None:
    report = _natural_systems_shaped_report()
    cross_paper = dict(report["cross_paper_evidence"])
    valid = {
        "severity": "error",
        "code": "cross_paper_evidence.invalid",
        "sidecar": "annotations/a.json",
        "annotation": "annotation:a",
        "reason": "invalid",
        "detail": "invalid annotation",
    }
    cross_paper["findings"] = [
        dict(valid) for _ in range(SECTION_ROW_CAP)
    ] + [{key: value for key, value in valid.items() if key != "detail"}]
    report["cross_paper_evidence"] = cross_paper
    with pytest.raises(
        ValueError,
        match=rf"cross_paper_evidence\.findings\[{SECTION_ROW_CAP}\].*detail",
    ):
        project_health_report(report, threshold="warn")


def test_layered_claim_rows_require_full_producer_shape() -> None:
    report = _natural_systems_shaped_report()
    layered = dict(report["layered_claims"])
    layered["migration_issues"] = [{"proposition": "p1"}]
    report["layered_claims"] = layered
    with pytest.raises(
        ValueError,
        match=r"layered_claims\.migration_issues\[0\].*source_path",
    ):
        project_health_report(report, threshold="warn")


def test_meta_timing_requires_name_and_duration() -> None:
    report = _natural_systems_shaped_report()
    report["_meta"] = {
        "timings": [{"name": "validate"}],
        "total_duration_seconds": 0.5,
    }
    with pytest.raises(
        ValueError,
        match=r"_meta\.timings\[0\].*duration_seconds",
    ):
        project_health_report(report, threshold="warn")


@pytest.mark.parametrize("total_issues", [362, 364])
def test_total_issues_must_equal_the_full_issue_count(total_issues: int) -> None:
    report = _natural_systems_shaped_report()
    report["total_issues"] = total_issues
    with pytest.raises(ValueError, match=r"total_issues.*count_issues"):
        project_health_report(report, threshold="warn")


def test_one_issue_cannot_claim_total_zero() -> None:
    report = _natural_systems_shaped_report()
    report["validation"] = [report["validation"][0]]
    report["unresolved_refs"] = []
    report["total_issues"] = 0
    with pytest.raises(ValueError, match=r"total_issues.*count_issues"):
        project_health_report(report, threshold="warn")


def test_dataset_anomaly_beyond_cap_requires_full_producer_shape() -> None:
    report = _natural_systems_shaped_report()
    valid = {
        "code": "dataset_stale_review",
        "severity": "warning",
        "entity_id": "dataset:a",
        "file_path": "entities/datasets/a.md",
        "message": "review is stale",
    }
    report["dataset_anomalies"] = [
        dict(valid) for _ in range(SECTION_ROW_CAP)
    ] + [{key: value for key, value in valid.items() if key != "message"}]
    with pytest.raises(
        ValueError,
        match=rf"dataset_anomalies\[{SECTION_ROW_CAP}\].*message",
    ):
        project_health_report(report, threshold="warn")


def test_filtered_prose_finding_requires_full_producer_shape() -> None:
    report = _natural_systems_shaped_report()
    prose = dict(report["prose_epistemics"])
    prose["findings"] = [
        {
            "code": "undeclared_grounding_report",
            "severity": "info",
            "counts_as_issue": False,
            "source_ref": "prose-source:a",
            "path": "data/prose-grounding/a/grounding.json",
        }
    ]
    report["prose_epistemics"] = prose
    with pytest.raises(
        ValueError,
        match=r"prose_epistemics\.findings\[0\].*message",
    ):
        project_health_report(report, threshold="warn")
