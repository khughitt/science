from __future__ import annotations

import pytest

from science_tool.graph.health_count import count_issues


def _report(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "unresolved_refs": [],
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
        "validation": [],
        "accepted_validation": [],
        "unwired_checks": [],
        "managed_artifacts": [],
        "layered_claims": _layered(),
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
        "total_issues": 0,
    }
    base.update(overrides)
    return base


def _layered(**overrides: object) -> dict[str, object]:
    """The real LayeredClaimHealthReport shape (graph/health.py:185) -- all four keys."""
    base: dict[str, object] = {
        "proposition_claim_layer_coverage": {"numerator": 0, "denominator": 0, "fraction": 0.0},
        "causal_leaning_identification_coverage": {"numerator": 0, "denominator": 0, "fraction": 0.0},
        "rival_model_packets_missing_discriminating_predictions": [],
        "migration_issues": [],
    }
    base.update(overrides)
    return base


def test_empty_report_counts_zero() -> None:
    assert count_issues(_report()) == 0


def test_health_aggregator_does_not_reexport_count_issues() -> None:
    from science_tool.graph import health

    assert not hasattr(health, "count_issues")


def test_rival_model_gaps_count_alongside_migration_issues() -> None:
    """health.py:342 sums BOTH lists into layered_claim_issue_count."""
    layered = _layered(
        migration_issues=[{"proposition": "p"}],
        rival_model_packets_missing_discriminating_predictions=[{"proposition": "p", "packet_id": "k"}] * 2,
    )
    assert count_issues(_report(layered_claims=layered)) == 3


def test_each_incomplete_coverage_metric_counts_as_one_gap() -> None:
    """coverage_gaps is derived from the two CoverageMetrics, not a report key."""
    layered = _layered(
        proposition_claim_layer_coverage={"numerator": 3, "denominator": 10, "fraction": 0.3},
        causal_leaning_identification_coverage={"numerator": 5, "denominator": 5, "fraction": 1.0},
    )
    assert count_issues(_report(layered_claims=layered)) == 1


def test_complete_coverage_contributes_no_gap() -> None:
    layered = _layered(
        proposition_claim_layer_coverage={"numerator": 4, "denominator": 4, "fraction": 1.0},
        causal_leaning_identification_coverage={"numerator": 5, "denominator": 5, "fraction": 1.0},
    )
    assert count_issues(_report(layered_claims=layered)) == 0


def test_zero_denominator_coverage_contributes_no_gap() -> None:
    """An empty denominator means "nothing to cover", not "a gap"."""
    assert count_issues(_report()) == 0


def test_validation_rows_each_count() -> None:
    assert count_issues(_report(validation=[{"severity": "warning"}] * 7)) == 7


def test_managed_artifacts_count_only_when_flagged() -> None:
    artifacts = [{"counts_as_issue": True}, {"counts_as_issue": False}]
    assert count_issues(_report(managed_artifacts=artifacts)) == 1


def test_unresolved_refs_count() -> None:
    assert count_issues(_report(unresolved_refs=[{"ref": "a"}, {"ref": "b"}])) == 2


def test_nested_findings_count() -> None:
    cross_paper = {
        "status": "fail",
        "empty_state": "active",
        "summary": {},
        "findings": [{"severity": "error"}] * 3,
        "propositions": [],
    }
    report = _report(cross_paper_evidence=cross_paper)
    assert count_issues(report) == 3


@pytest.mark.parametrize(
    "key",
    ["validation", "layered_claims", "cross_paper_evidence", "prose_epistemics"],
)
def test_missing_required_section_is_rejected(key: str) -> None:
    report = _report()
    del report[key]
    with pytest.raises(ValueError, match=key):
        count_issues(report)


@pytest.mark.parametrize(
    ("key", "value"),
    [("validation", {}), ("layered_claims", [])],
)
def test_wrong_section_type_is_rejected(key: str, value: object) -> None:
    with pytest.raises(TypeError, match=key):
        count_issues(_report(**{key: value}))


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("cross_paper_evidence", {}),
        ("cross_paper_evidence", {"findings": {}}),
        ("prose_epistemics", {}),
        ("prose_epistemics", {"findings": None}),
    ],
)
def test_nested_findings_must_exist_and_be_a_list(section: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError), match="findings"):
        count_issues(_report(**{section: value}))


@pytest.mark.parametrize(
    "key",
    ["migration_issues", "rival_model_packets_missing_discriminating_predictions"],
)
def test_layered_issue_lists_are_required(key: str) -> None:
    layered = _layered()
    del layered[key]
    with pytest.raises(ValueError, match=key):
        count_issues(_report(layered_claims=layered))


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        ("proposition_claim_layer_coverage", {"numerator": 0, "fraction": 1.0}),
        ("causal_leaning_identification_coverage", {"numerator": "zero", "denominator": 0, "fraction": 1.0}),
    ],
)
def test_coverage_metrics_reject_missing_or_wrong_typed_fields(metric: str, value: object) -> None:
    layered = _layered(**{metric: value})
    with pytest.raises((TypeError, ValueError), match=metric):
        count_issues(_report(layered_claims=layered))


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
        "dataset_anomalies",
        "schema_invalid",
        "managed_artifacts",
        "tooling_scaffold",
        "validation",
        "accepted_validation",
        "unwired_checks",
    ],
)
def test_root_row_sections_reject_non_mapping_members(section: str) -> None:
    with pytest.raises(TypeError, match=rf"{section}\[0\]"):
        count_issues(_report(**{section: [None]}))


@pytest.mark.parametrize(
    "section",
    ["migration_issues", "rival_model_packets_missing_discriminating_predictions"],
)
def test_layered_issue_lists_reject_non_mapping_members(section: str) -> None:
    layered = _layered(**{section: [None]})
    with pytest.raises(TypeError, match=rf"{section}\[0\]"):
        count_issues(_report(layered_claims=layered))


@pytest.mark.parametrize("section", ["cross_paper_evidence", "prose_epistemics"])
def test_nested_findings_reject_non_mapping_members(section: str) -> None:
    report_section = dict(_report()[section])
    report_section["findings"] = [None]
    with pytest.raises(TypeError, match=rf"{section}\.findings\[0\]"):
        count_issues(_report(**{section: report_section}))


@pytest.mark.parametrize(
    ("section", "row"),
    [
        ("managed_artifacts", {}),
        ("managed_artifacts", {"counts_as_issue": "yes"}),
        ("prose_epistemics", {}),
        ("prose_epistemics", {"counts_as_issue": 1}),
    ],
)
def test_issue_membership_flag_is_required_and_boolean(
    section: str, row: dict[str, object]
) -> None:
    if section == "managed_artifacts":
        report = _report(managed_artifacts=[row])
    else:
        prose = dict(_report()["prose_epistemics"])
        prose["findings"] = [row]
        report = _report(prose_epistemics=prose)
    with pytest.raises((TypeError, ValueError), match="counts_as_issue"):
        count_issues(report)


def test_prose_findings_count_only_when_flagged() -> None:
    prose = dict(_report()["prose_epistemics"])
    prose["findings"] = [
        {"counts_as_issue": True},
        {"counts_as_issue": False},
    ]
    assert count_issues(_report(prose_epistemics=prose)) == 1
