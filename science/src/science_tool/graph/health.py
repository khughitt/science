"""Deterministic assembly for ``science health``."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from science_model.audit import AuditReport, ReportedFinding

from science_tool.findings.catalog import (
    build_project_registry,
    build_registry_for_entity_registry,
)
from science_tool.findings.producers import (
    FindingProducerResult,
    validate_producer_result,
)
from science_tool.findings.reporting import build_audit_report
from science_tool.graph.health_checks import HEALTH_CHECKS, HealthCheck, HealthContext
from science_tool.graph.health_checks.schema_invalid import (
    SCHEMA_INVALID_PRODUCER,
    produce_schema_invalid,
)
from science_tool.graph.sources import load_project_sources
from science_tool.instruments import InstrumentResult
from science_tool.validate.acceptance import partition_health_acceptances


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
    requested = (
        frozenset(check.name for check in HEALTH_CHECKS if not check.requires_sources)
        if fast
        else frozenset(checks or known_names)
    )
    skipped = frozenset(skip_checks or ())
    unknown = (requested | skipped) - known_names
    if unknown:
        names = ", ".join(sorted(unknown))
        known = ", ".join(sorted(known_names))
        raise ValueError(f"unknown health check(s): {names}; known checks: {known}")
    selected_names = requested - skipped
    return tuple(check for check in HEALTH_CHECKS if check.name in selected_names)


def _partition_validation_acceptances(
    project_root: Path,
    producer_results: dict[str, FindingProducerResult],
) -> tuple[dict[str, FindingProducerResult], tuple]:
    validate_result = producer_results.get("validate")
    if validate_result is None or validate_result.instrument.status == "unwired":
        return producer_results, ()
    reported = [ReportedFinding(producer_id="validate", finding=finding) for finding in validate_result.instrument.rows]
    remaining, accepted = partition_health_acceptances(project_root, reported)
    producer_results = dict(producer_results)
    producer_results["validate"] = FindingProducerResult(
        instrument=InstrumentResult.from_rows(
            [item.finding for item in remaining],
            code=validate_result.instrument.code,
            reason=validate_result.instrument.reason,
        ),
        metrics=validate_result.metrics,
    )
    return producer_results, tuple(accepted)


def build_health_report(
    project_root: Path,
    *,
    ingestion_ref: str,
    generated_at: str,
    collect_timings: bool = False,
    checks: set[str] | frozenset[str] | None = None,
    skip_checks: set[str] | frozenset[str] | None = None,
    fast: bool = False,
) -> AuditReport:
    """Run selected producers and assemble their already-validated observations."""
    project_root = project_root.resolve()
    selected_checks = _select_health_checks(
        checks=checks,
        skip_checks=skip_checks,
        fast=fast,
    )
    context = HealthContext(
        project_root=project_root,
        collect_timings=collect_timings,
        selected_checks=selected_checks,
    )
    started = perf_counter()
    if any(check.requires_sources for check in selected_checks):
        context.sources = context.run(
            "load_project_sources",
            lambda: load_project_sources(
                project_root,
                strict_core_schema=False,
                strict_identity=False,
            ),
        )
        registry = build_registry_for_entity_registry(context.sources.registry)
    else:
        registry = build_project_registry(project_root)

    producer_results: dict[str, FindingProducerResult] = {}
    if context.sources is not None:
        schema_result = produce_schema_invalid(context.sources.skipped_entities)
        producer_results[SCHEMA_INVALID_PRODUCER.producer_id] = validate_producer_result(
            registry,
            SCHEMA_INVALID_PRODUCER.producer_id,
            schema_result,
        )

    for check in selected_checks:
        result = context.run(check.name, lambda check=check: check.run(context))
        producer_results[check.producer.producer_id] = validate_producer_result(
            registry,
            check.producer.producer_id,
            result,
        )

    producer_results, accepted = _partition_validation_acceptances(
        project_root,
        producer_results,
    )
    elapsed = perf_counter() - started
    return build_audit_report(
        producer_results=producer_results,
        registry=registry,
        ingestion_ref=ingestion_ref,
        generated_at=generated_at,
        total_duration_seconds=elapsed,
        accepted=accepted,
        timings=tuple(context.timings),
    )
