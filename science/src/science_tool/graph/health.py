"""Aggregator for project health diagnostics.

Provides the data layer for `science health` — groups unresolved refs
by target, surfaces stale tasks, knowledge gaps, and schema issues. Output
is a structured dict suitable for both human display and agent consumption.
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import NotRequired, TypedDict, cast

from science_tool.graph.health_checks import (
    HEALTH_CHECKS,
    HealthCheck,
    HealthContext,
    HealthTiming,
    context_sources,
)
from science_tool.graph.health_checks.agent_context import AgentContextFinding
from science_tool.graph.health_checks.archive_lag import TaskArchiveLag
from science_tool.graph.health_checks.cross_paper_evidence import CrossPaperEvidenceHealthReport
from science_tool.graph.health_checks.entity_identity import EntityIdentityFinding
from science_tool.graph.health_checks.identity_policy import IdentityPolicyFinding
from science_tool.graph.health_checks.invalid_entity_aspects import InvalidEntityAspectsFinding
from science_tool.graph.health_checks.legacy_task_type import LegacyTaskTypeFinding
from science_tool.graph.health_checks.lingering_tags import LingeringTagsRecord
from science_tool.graph.health_checks.tooling_scaffold import ToolingScaffoldFinding
from science_tool.graph.health_checks.unregistered_ref_kinds import UnregisteredRefKind
from science_tool.graph.health_checks.unresolved_refs import UnresolvedRef
from science_tool.graph.health_checks.validate import ValidationFinding
from science_tool.graph.migrate import LayeredClaimMigrationReport
from science_tool.graph.health_count import count_issues
from science_tool.graph.sources import load_project_sources
from science_tool.instruments import InstrumentResult
from science_tool.validate.acceptance import accepted_validation_entries, entry_suppresses


class AcceptedValidationFinding(ValidationFinding):
    accepted_reason: str


class SchemaInvalidFinding(TypedDict):
    """A source entity dropped from the health sweep because it failed schema validation.

    Surfaced as a finding (rather than aborting the whole report) so a single
    malformed entity does not take the diagnostic offline (fb-2026-05-30-008).
    """

    code: str  # always "entity.schema-invalid"
    severity: str  # "error"
    kind: str
    path: str
    message: str


class UnwiredCheck(TypedDict):
    """A check that COULD NOT RUN. Its rows are meaningless and are not reported.

    This is deliberately NOT folded into ``total_issues``. An unwired check is not a
    finding about the project — it is a HOLE IN THE DIAGNOSTIC, and burying it in a
    count would re-hide exactly what it exists to expose. It gets its own list, and
    the renderer must refuse to call the project clean while this list is non-empty.
    """

    check: str
    code: str
    reason: str | None


class HealthReport(TypedDict):
    unresolved_refs: list[UnresolvedRef]
    unregistered_ref_kinds: list[UnregisteredRefKind]
    lingering_tags_lines: list[LingeringTagsRecord]
    agent_context: list[AgentContextFinding]
    identity_policy: list["IdentityPolicyFinding"]
    entity_identity: list[EntityIdentityFinding]
    layered_claims: "LayeredClaimHealthReport"
    cross_paper_evidence: "CrossPaperEvidenceHealthReport"
    legacy_task_type: list["LegacyTaskTypeFinding"]
    invalid_entity_aspects: list["InvalidEntityAspectsFinding"]
    dataset_anomalies: list[dict]
    schema_invalid: list[SchemaInvalidFinding]
    archive_lag: TaskArchiveLag
    managed_artifacts: list[dict]
    tooling_scaffold: list[ToolingScaffoldFinding]
    validation: list[ValidationFinding]
    accepted_validation: list[AcceptedValidationFinding]
    prose_epistemics: dict[str, object]
    unwired_checks: list[UnwiredCheck]
    total_issues: int
    _meta: NotRequired["HealthMeta"]


class HealthMeta(TypedDict):
    timings: list[HealthTiming]
    total_duration_seconds: float


def _run_health_checks(context: HealthContext) -> dict[str, object]:
    results: dict[str, object] = {}
    for check in context.selected_checks:
        results[check.name] = context.run(check.name, lambda check=check: check.run(context))
    return results


def _drain_instrument_results(
    results: dict[str, object],
) -> tuple[dict[str, object], list[UnwiredCheck]]:
    """Unpack every ``InstrumentResult`` into rows, diverting the unwired ones.

    An unwired check contributes NO rows to the report — they are meaningless by the
    type's own invariant — and instead surfaces as an ``UnwiredCheck``. Checks that do
    not (yet) return an ``InstrumentResult`` pass through untouched.
    """
    rows: dict[str, object] = {}
    unwired: list[UnwiredCheck] = []
    for name, value in results.items():
        if not isinstance(value, InstrumentResult):
            rows[name] = value
            continue
        if value.status == "unwired":
            if value.code is None:  # pragma: no cover — the model validator forbids it
                raise RuntimeError(f"health check {name!r} returned unwired without a code")
            unwired.append({"check": name, "code": value.code, "reason": value.reason})
            rows[name] = []
            continue
        rows[name] = value.rows
    unwired.sort(key=lambda row: row["check"])
    return rows, unwired


def _partition_accepted_validation_findings(
    project_root: Path,
    findings: list[ValidationFinding],
) -> tuple[list[ValidationFinding], list[AcceptedValidationFinding]]:
    entries = accepted_validation_entries(project_root)
    if not entries:
        return findings, []
    remaining: list[ValidationFinding] = []
    accepted: list[AcceptedValidationFinding] = []
    for finding in findings:
        match = next(
            (
                entry
                for entry in entries
                if entry_suppresses(
                    entry,
                    rule=finding.get("rule"),
                    severity=finding.get("severity") or "",
                    path=finding.get("path"),
                    task=finding.get("task"),
                    message=finding.get("message") or "",
                )
            ),
            None,
        )
        if match is None:
            remaining.append(finding)
            continue
        reason = match.get("reason")
        accepted.append({**finding, "accepted_reason": str(reason).strip()})
    return remaining, accepted


class CoverageMetric(TypedDict):
    numerator: int
    denominator: int
    fraction: float


class RivalModelGap(TypedDict):
    proposition: str
    source_path: str
    packet_id: str


class LayeredClaimIssue(TypedDict):
    proposition: str
    source_path: str
    warnings: list[str]
    todos: list[str]


class LayeredClaimHealthReport(TypedDict):
    proposition_claim_layer_coverage: CoverageMetric
    causal_leaning_identification_coverage: CoverageMetric
    rival_model_packets_missing_discriminating_predictions: list[RivalModelGap]
    migration_issues: list[LayeredClaimIssue]


def _health_check_names() -> frozenset[str]:
    return frozenset(check.name for check in HEALTH_CHECKS)


def list_health_checks() -> list[dict[str, object]]:
    return [
        {
            "name": check.name,
            "description": check.description,
            "requires_sources": check.requires_sources,
        }
        for check in HEALTH_CHECKS
    ]


def _select_health_checks(
    *,
    checks: set[str] | frozenset[str] | None,
    skip_checks: set[str] | frozenset[str] | None,
    fast: bool,
) -> tuple[HealthCheck, ...]:
    known_names = _health_check_names()
    if fast and checks:
        raise ValueError("cannot combine --fast and --check")
    if fast:
        requested = frozenset(check.name for check in HEALTH_CHECKS if not check.requires_sources)
    else:
        requested = frozenset(checks or known_names)
    skipped = frozenset(skip_checks or ())
    unknown = (requested | skipped) - known_names
    if unknown:
        names = ", ".join(sorted(unknown))
        known = ", ".join(sorted(known_names))
        raise ValueError(f"unknown health check(s): {names}; known checks: {known}")
    selected_names = requested - skipped
    return tuple(check for check in HEALTH_CHECKS if check.name in selected_names)


def _empty_check_results(project_root: Path) -> dict[str, object]:
    return {check.name: check.empty(project_root) for check in HEALTH_CHECKS}


def build_health_report(
    project_root: Path,
    *,
    collect_timings: bool = False,
    checks: set[str] | frozenset[str] | None = None,
    skip_checks: set[str] | frozenset[str] | None = None,
    fast: bool = False,
) -> HealthReport:
    """Aggregate all health checks for a project."""
    project_root = project_root.resolve()
    selected_checks = _select_health_checks(checks=checks, skip_checks=skip_checks, fast=fast)
    context = HealthContext(
        project_root=project_root,
        collect_timings=collect_timings,
        selected_checks=selected_checks,
    )
    total_started = perf_counter()
    needs_sources = any(check.requires_sources for check in selected_checks)
    if needs_sources:
        # Health is a diagnostic sweep: a single schema-invalid core entity must
        # NOT abort the whole report (fb-2026-05-30-008). Load non-strict and
        # surface the dropped entities as `schema_invalid` findings below.
        context.sources = context.run(
            "load_project_sources",
            lambda: load_project_sources(project_root, strict_core_schema=False, strict_identity=False),
        )
    check_results = _empty_check_results(project_root)
    check_rows, unwired_checks = _drain_instrument_results(_run_health_checks(context))
    check_results.update(check_rows)
    identity_policy_findings = cast("list[IdentityPolicyFinding]", check_results["identity_policy"])
    entity_identity = cast("list[EntityIdentityFinding]", check_results.get("entity_identity", []))
    layered_claims_enabled = "layered_claim_migration" in {check.name for check in selected_checks}
    proposition_entities = (
        [entity for entity in context_sources(context).entities if entity.kind == "proposition"]
        if layered_claims_enabled
        else []
    )
    migration_report = cast(LayeredClaimMigrationReport, check_results["layered_claim_migration"])
    cross_paper_evidence = cast(
        "CrossPaperEvidenceHealthReport",
        check_results["cross_paper_evidence"],
    )
    causal_leaning_rows = [
        row
        for row in migration_report["rows"]
        if row["authored_claim_layer"] in {"causal_effect", "mechanistic_narrative"}
        or row["authored_identification_strength"] is not None
        or row["inferred_identification_strength"] is not None
        or any("mechanistic" in warning.lower() for warning in row["warnings"])
    ]
    rival_model_gaps: list[RivalModelGap] = []
    for entity in proposition_entities:
        # `rival_model_packet` lives on ProjectEntity; defensive getattr for bare Entity instances.
        packet = getattr(entity, "rival_model_packet", None)
        if packet is None or packet.discriminating_predictions:
            continue
        rival_model_gaps.append(
            {
                "proposition": entity.canonical_id,
                "source_path": entity.file_path,
                "packet_id": packet.packet_id,
            }
        )

    migration_issues: list[LayeredClaimIssue] = [
        {
            "proposition": row["proposition"],
            "source_path": row["source_path"],
            "warnings": row["warnings"],
            "todos": row["todos"],
        }
        for row in migration_report["rows"]
        if row["warnings"] or row["todos"]
    ]

    archive_lag = cast("TaskArchiveLag", check_results["archive_lag"])
    managed_artifacts = cast("list[dict]", check_results["managed_artifacts"])
    tooling_scaffold = cast("list[ToolingScaffoldFinding]", check_results["tooling_scaffold"])
    unresolved_refs = cast("list[UnresolvedRef]", check_results["unresolved_refs"])
    unregistered_ref_kinds = cast("list[UnregisteredRefKind]", check_results["unregistered_ref_kinds"])
    lingering_tags_lines = cast("list[LingeringTagsRecord]", check_results["lingering_tags"])
    agent_context = cast("list[AgentContextFinding]", check_results["agent_context"])
    dataset_anomalies = cast("list[dict]", check_results["dataset_anomalies"])
    schema_invalid: list[SchemaInvalidFinding] = [
        {
            "code": "entity.schema-invalid",
            "severity": "error",
            "kind": skipped.kind,
            "path": skipped.path,
            "message": skipped.details,
        }
        for skipped in (context.sources.skipped_entities if context.sources is not None else [])
        if skipped.reason == "core_schema_validation_failed"
    ]
    legacy_task_type = cast("list[LegacyTaskTypeFinding]", check_results["legacy_task_type"])
    invalid_entity_aspects = cast("list[InvalidEntityAspectsFinding]", check_results["invalid_entity_aspects"])
    validation, accepted_validation = _partition_accepted_validation_findings(
        project_root,
        cast("list[ValidationFinding]", check_results["validate"]),
    )
    prose_epistemics = cast("dict[str, object]", check_results["prose_epistemics"])
    proposition_coverage = _coverage_metric(
        numerator=sum(1 for entity in proposition_entities if entity.claim_layer is not None),
        denominator=len(proposition_entities),
    )
    causal_coverage = _coverage_metric(
        numerator=sum(1 for row in causal_leaning_rows if row["authored_identification_strength"] is not None),
        denominator=len(causal_leaning_rows),
    )
    layered_claims: LayeredClaimHealthReport = {
        "proposition_claim_layer_coverage": proposition_coverage,
        "causal_leaning_identification_coverage": causal_coverage,
        "rival_model_packets_missing_discriminating_predictions": rival_model_gaps,
        "migration_issues": migration_issues,
    }

    report: HealthReport = {
        "unresolved_refs": unresolved_refs,
        "unregistered_ref_kinds": unregistered_ref_kinds,
        "lingering_tags_lines": lingering_tags_lines,
        "agent_context": agent_context,
        "identity_policy": identity_policy_findings,
        "entity_identity": entity_identity,
        "layered_claims": layered_claims,
        "cross_paper_evidence": cross_paper_evidence,
        "legacy_task_type": legacy_task_type,
        "invalid_entity_aspects": invalid_entity_aspects,
        "dataset_anomalies": dataset_anomalies,
        "schema_invalid": schema_invalid,
        "archive_lag": cast("TaskArchiveLag", archive_lag),
        "managed_artifacts": cast("list[dict]", managed_artifacts),
        "tooling_scaffold": tooling_scaffold,
        "validation": validation,
        "accepted_validation": accepted_validation,
        "prose_epistemics": prose_epistemics,
        "unwired_checks": unwired_checks,
        "total_issues": 0,
    }
    report["total_issues"] = count_issues(report)
    if collect_timings:
        report["_meta"] = {
            "timings": context.timings,
            "total_duration_seconds": perf_counter() - total_started,
        }
    return report


def _coverage_metric(*, numerator: int, denominator: int) -> CoverageMetric:
    fraction = 1.0 if denominator == 0 else numerator / denominator
    return {
        "numerator": numerator,
        "denominator": denominator,
        "fraction": fraction,
    }
