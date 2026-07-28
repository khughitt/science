from pydantic import BaseModel, ConfigDict

from science_model.audit import (
    AcceptedFinding,
    AuditFinding,
    FindingRule,
    FindingSection,
    finding_fingerprint,
)
from science_model.audit.subjects import EntitySubject
from science_tool.findings.producers import (
    FindingProducer,
    FindingProducerResult,
    build_registry,
)
from science_tool.instruments import InstrumentResult


class _Qualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Metrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scanned: int


class _IdentityQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant: str


def _finding(
    rule_id: str,
    *,
    ref: str,
    severity: str,
    qualifiers: dict[str, object] | None = None,
) -> AuditFinding:
    return AuditFinding(
        rule_id=rule_id,
        subject=EntitySubject(ref=ref),
        severity=severity,
        qualifiers=qualifiers or {},
        message=rule_id,
        evidence=[],
    )


def test_build_audit_report_orders_rows_and_separates_output_channels():
    from science_tool.findings.reporting import build_audit_report

    sections = (
        FindingSection(id="first", title="First", section_order=10),
        FindingSection(id="second", title="Second", section_order=20),
    )
    rules = (
        FindingRule(
            id="first.alpha",
            severities={"error", "warn", "info"},
            subject_types={"entity"},
            qualifier_schema=_IdentityQualifiers,
            identity_qualifiers=("variant",),
            title="a",
            section="first",
            display_order=20,
        ),
        FindingRule(
            id="first.beta",
            severities={"error", "warn", "info"},
            subject_types={"entity"},
            qualifier_schema=_Qualifiers,
            title="b",
            section="first",
            display_order=10,
        ),
        FindingRule(
            id="second.gamma",
            severities={"error", "warn", "info"},
            subject_types={"entity"},
            qualifier_schema=_Qualifiers,
            title="g",
            section="second",
            display_order=10,
        ),
    )
    registry = build_registry(
        [
            FindingProducer(
                producer_id="wired",
                namespace="health_checks",
                source_module="graph/health_checks/wired.py",
                rules=rules,
                sections=sections,
                metrics_schema=_Metrics,
            ),
            FindingProducer(
                producer_id="unwired",
                namespace="data_audit",
                source_module="graph/health_checks/unwired.py",
                rules=(),
                sections=(),
                metrics_schema=None,
            ),
        ],
        active_kinds=frozenset(),
    )
    same_subject = [
        _finding(
            "first.alpha",
            ref="dataset:z",
            severity="info",
            qualifiers={"variant": variant},
        )
        for variant in ("b", "a")
    ]
    results = {
        "wired": FindingProducerResult(
            instrument=InstrumentResult.ok(
                [
                    _finding("second.gamma", ref="dataset:z", severity="warn"),
                    _finding(
                        "first.alpha",
                        ref="dataset:a",
                        severity="info",
                        qualifiers={"variant": "a"},
                    ),
                    *same_subject,
                    _finding(
                        "first.alpha",
                        ref="dataset:y",
                        severity="error",
                        qualifiers={"variant": "a"},
                    ),
                    _finding("first.beta", ref="dataset:z", severity="warn"),
                ],
                code="partial",
                reason="one upstream source skipped",
            ),
            metrics={"scanned": 6},
        ),
        "unwired": FindingProducerResult(
            instrument=InstrumentResult.unwired(code="not-configured", reason="missing token")
        ),
    }
    accepted = AcceptedFinding(
        producer_id="wired",
        finding=_finding("first.beta", ref="dataset:accepted", severity="warn"),
        acceptance_key="a" * 32,
        reason="known exception",
    )

    report = build_audit_report(
        producer_results=results,
        registry=registry,
        ingestion_ref="run:1",
        generated_at="2026-07-28T12:00:00+00:00",
        total_duration_seconds=1.0,
        accepted=(accepted,),
    )

    expected_same_subject = sorted(
        same_subject,
        key=lambda finding: finding_fingerprint(
            rule_id=finding.rule_id,
            subject=finding.subject,
            identity_qualifiers={"variant": finding.qualifiers["variant"]},
        ),
    )
    assert [
        (
            row.finding.rule_id,
            row.finding.severity,
            row.finding.subject.ref,
            row.finding.qualifiers.get("variant"),
        )
        for row in report.findings
    ] == [
        ("first.beta", "warn", "dataset:z", None),
        ("first.alpha", "error", "dataset:y", "a"),
        ("first.alpha", "info", "dataset:a", "a"),
        *[("first.alpha", "info", "dataset:z", finding.qualifiers["variant"]) for finding in expected_same_subject],
        ("second.gamma", "warn", "dataset:z", None),
    ]
    assert report.accepted == (accepted,)
    assert report.metrics["wired"].model_dump() == {"scanned": 6}
    assert "unwired" not in report.metrics
    assert report.totals.model_dump() == {
        "findings_total": 6,
        "findings_by_severity": {"error": 1, "warn": 2, "info": 3},
        "accepted_total": 1,
        "unwired_total": 1,
    }
    producers_run = set(report.meta.producers_run)
    unwired_producers = {item.producer_id for item in report.unwired}
    assert producers_run == {"wired"}
    assert unwired_producers == {"unwired"}
    assert producers_run.isdisjoint(unwired_producers)
    assert report.caveats[0].producer_id == "wired"
