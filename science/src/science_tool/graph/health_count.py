"""Strict issue counting for complete and projected health reports."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from science_tool.graph.health_checks.archive_lag import TaskArchiveLag, archive_lag_total


def _required(container: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in container:
        raise ValueError(f"{path} is missing required field {key!r}")
    return container[key]


def _mapping(container: Mapping[str, Any], key: str, path: str) -> Mapping[str, Any]:
    value = _required(container, key, path)
    if not isinstance(value, Mapping):
        raise TypeError(f"{path}.{key} must be a mapping, got {type(value).__name__}")
    return value


def _mapping_members(value: list[Any], path: str) -> list[Mapping[str, Any]]:
    for index, member in enumerate(value):
        if not isinstance(member, Mapping):
            raise TypeError(f"{path}[{index}] must be a mapping, got {type(member).__name__}")
    return cast("list[Mapping[str, Any]]", value)


def _rows(report: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = _required(report, key, "health report")
    if not isinstance(value, list):
        raise TypeError(f"health report.{key} must be a list, got {type(value).__name__}")
    return _mapping_members(value, f"health report.{key}")


def _findings(report: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    section = _mapping(report, key, "health report")
    findings = _required(section, "findings", f"health report.{key}")
    if not isinstance(findings, list):
        raise TypeError(
            f"health report.{key}.findings must be a list, "
            f"got {type(findings).__name__}"
        )
    return _mapping_members(findings, f"health report.{key}.findings")


def _count_issue_flags(findings: list[Mapping[str, Any]], path: str) -> int:
    count = 0
    for index, finding in enumerate(findings):
        flag = _required(finding, "counts_as_issue", f"{path}[{index}]")
        if type(flag) is not bool:
            raise TypeError(
                f"{path}[{index}].counts_as_issue must be a bool, "
                f"got {type(flag).__name__}"
            )
        count += int(flag)
    return count


def _validate_archive_lag(report: Mapping[str, Any]) -> int:
    archive_lag = _mapping(report, "archive_lag", "health report")
    for key in ("done_in_active", "retired_in_active", "missing_completed"):
        value = _required(archive_lag, key, "health report.archive_lag")
        if type(value) is not int:
            raise TypeError(
                f"health report.archive_lag.{key} must be an int, "
                f"got {type(value).__name__}"
            )
    return archive_lag_total(cast("TaskArchiveLag", archive_lag))


def _count_layered_claim_issues(report: Mapping[str, Any]) -> int:
    layered = _mapping(report, "layered_claims", "health report")
    migration_issues = _required(layered, "migration_issues", "health report.layered_claims")
    rival_model_gaps = _required(
        layered,
        "rival_model_packets_missing_discriminating_predictions",
        "health report.layered_claims",
    )
    for key, value in (
        ("migration_issues", migration_issues),
        ("rival_model_packets_missing_discriminating_predictions", rival_model_gaps),
    ):
        if not isinstance(value, list):
            raise TypeError(
                f"health report.layered_claims.{key} must be a list, "
                f"got {type(value).__name__}"
            )
    issues = len(
        _mapping_members(
            migration_issues,
            "health report.layered_claims.migration_issues",
        )
    ) + len(
        _mapping_members(
            rival_model_gaps,
            "health report.layered_claims."
            "rival_model_packets_missing_discriminating_predictions",
        )
    )
    for key in (
        "proposition_claim_layer_coverage",
        "causal_leaning_identification_coverage",
    ):
        metric = _mapping(layered, key, "health report.layered_claims")
        for field in ("numerator", "denominator"):
            value = _required(metric, field, f"health report.layered_claims.{key}")
            if type(value) is not int:
                raise TypeError(
                    f"health report.layered_claims.{key}.{field} must be an int, "
                    f"got {type(value).__name__}"
                )
        fraction = _required(metric, "fraction", f"health report.layered_claims.{key}")
        if not isinstance(fraction, (int, float)) or isinstance(fraction, bool):
            raise TypeError(
                f"health report.layered_claims.{key}.fraction must be numeric, "
                f"got {type(fraction).__name__}"
            )
        if metric["denominator"] > 0 and metric["numerator"] < metric["denominator"]:
            issues += 1
    return issues


def count_issues(report: Mapping[str, Any]) -> int:
    """Return the issue count after strictly validating the complete report shape.

    The same function runs over the full report and its projection, making displayed and
    total issue counts comparable. It is deliberately not a plain row count:
    ``managed_artifacts`` uses ``counts_as_issue``, coverage gaps are derived from
    metrics, and non-zero archive lag contributes one issue.
    """
    row_sections = (
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
    )
    rows = {key: _rows(report, key) for key in row_sections}
    total_issues = _required(report, "total_issues", "health report")
    if type(total_issues) is not int:
        raise TypeError(
            f"health report.total_issues must be an int, got {type(total_issues).__name__}"
        )

    lag_total = _validate_archive_lag(report)
    layered_issues = _count_layered_claim_issues(report)
    prose_findings = _findings(report, "prose_epistemics")
    cross_paper_findings = _findings(report, "cross_paper_evidence")
    managed_artifact_issues = _count_issue_flags(
        rows["managed_artifacts"],
        "health report.managed_artifacts",
    )
    prose_issues = _count_issue_flags(
        prose_findings,
        "health report.prose_epistemics.findings",
    )
    return (
        len(rows["unresolved_refs"])
        + len(rows["unregistered_ref_kinds"])
        + len(rows["lingering_tags_lines"])
        + len(rows["agent_context"])
        + len(rows["identity_policy"])
        + len(rows["entity_identity"])
        + layered_issues
        + len(rows["dataset_anomalies"])
        + len(rows["schema_invalid"])
        + (1 if lag_total else 0)
        + managed_artifact_issues
        + len(rows["tooling_scaffold"])
        + len(rows["validation"])
        + prose_issues
        + len(cross_paper_findings)
    )
