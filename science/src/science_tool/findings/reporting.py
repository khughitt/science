"""Deterministic assembly of trusted producer results into an audit report."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from science_model.audit import (
    AcceptedFinding,
    AuditFinding,
    AuditReport,
    ProducerCaveat,
    ProducerMetrics,
    ReportMeta,
    ReportTotals,
    ReportedFinding,
    UnwiredProducer,
    finding_fingerprint,
)
from science_model.audit.fingerprint import canonical_json

from science_tool.findings.producers import (
    FindingProducerResult,
    FindingRegistry,
    RegistryError,
    validate_finding,
    validate_producer_result,
)

_SEVERITY_RANK = {"error": 0, "warn": 1, "info": 2}


def report_sort_key(registry: FindingRegistry, finding: AuditFinding) -> tuple[object, ...]:
    rule = registry.rule(finding.rule_id)
    finding_id = finding_fingerprint(
        rule_id=finding.rule_id,
        subject=finding.subject,
        identity_qualifiers=rule.identity_subset(finding.qualifiers),
    )
    return (
        *registry.sort_key(finding.rule_id),
        _SEVERITY_RANK[finding.severity],
        canonical_json(finding.subject.model_dump(mode="json", exclude_none=True)),
        finding_id,
    )


def build_audit_report(
    *,
    producer_results: Mapping[str, FindingProducerResult],
    registry: FindingRegistry,
    ingestion_ref: str,
    generated_at: str,
    total_duration_seconds: float,
    accepted: tuple[AcceptedFinding, ...] = (),
    timings: tuple[Mapping[str, object], ...] = (),
) -> AuditReport:
    findings: list[ReportedFinding] = []
    metrics: dict[str, ProducerMetrics] = {}
    caveats: list[ProducerCaveat] = []
    unwired: list[UnwiredProducer] = []
    producers_run: list[str] = []
    for producer_id, raw in producer_results.items():
        result = validate_producer_result(registry, producer_id, raw)
        if result.instrument.status == "unwired":
            code = result.instrument.code
            if code is None:
                raise RegistryError(f"{producer_id!r} returned unwired without a code")
            unwired.append(
                UnwiredProducer(
                    producer_id=producer_id,
                    code=code,
                    reason=result.instrument.reason,
                )
            )
            continue
        producers_run.append(producer_id)
        if result.instrument.code is not None or result.instrument.reason is not None:
            caveats.append(
                ProducerCaveat(
                    producer_id=producer_id,
                    code=result.instrument.code,
                    reason=result.instrument.reason,
                )
            )
        producer = registry.producers_by_id[producer_id]
        if producer.metrics_schema is not None:
            metrics[producer_id] = result.metrics
        findings.extend(ReportedFinding(producer_id=producer_id, finding=finding) for finding in result.instrument.rows)
    for item in accepted:
        validate_finding(
            registry,
            item.producer_id,
            item.finding,
        )
    findings.sort(key=lambda item: report_sort_key(registry, item.finding))
    accepted = tuple(sorted(accepted, key=lambda item: report_sort_key(registry, item.finding)))
    severity = Counter(item.finding.severity for item in findings)
    return AuditReport(
        schema_version=2,
        fingerprint_version=1,
        ingestion_ref=ingestion_ref,
        generated_at=generated_at,
        findings=tuple(findings),
        accepted=accepted,
        metrics={key: metrics[key] for key in sorted(metrics)},
        caveats=tuple(sorted(caveats, key=lambda item: item.producer_id)),
        unwired=tuple(sorted(unwired, key=lambda item: item.producer_id)),
        totals=ReportTotals(
            findings_total=len(findings),
            findings_by_severity=dict(severity),
            accepted_total=len(accepted),
            unwired_total=len(unwired),
        ),
        meta=ReportMeta(
            producers_run=tuple(sorted(producers_run)),
            total_duration_seconds=total_duration_seconds,
            timings=timings,
        ),
    )
