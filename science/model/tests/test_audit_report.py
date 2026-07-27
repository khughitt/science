import pytest
from pydantic import ValidationError

from science_model.audit.finding import AuditFinding
from science_model.audit.report import (
    REPORT_SCHEMA_VERSION,
    AcceptedFinding,
    AuditReport,
    ProducerMetrics,
    ReportedFinding,
    UnwiredProducer,
)
from science_model.audit.subjects import EntitySubject


def _finding(ref="dataset:a", rule="dataset.stale-review") -> AuditFinding:
    return AuditFinding(
        rule_id=rule,
        subject=EntitySubject(ref=ref),
        severity="warn",
        qualifiers={},
        message="m",
        evidence=[],
    )


def _report(**overrides) -> AuditReport:
    base = dict(
        schema_version=REPORT_SCHEMA_VERSION,
        fingerprint_version=1,
        ingestion_ref="run:2026-07-27-curation-sweep-a3f1",
        generated_at="2026-07-27T12:00:00+00:00",
        findings=[ReportedFinding(producer_id="dataset_anomalies", finding=_finding())],
        accepted=[],
        metrics={},
        unwired=[],
        totals={
            "findings_total": 1,
            "findings_by_severity": {"warn": 1},
            "accepted_total": 0,
            "unwired_total": 0,
        },
        meta={
            "producers_run": ["dataset_anomalies"],
            "total_duration_seconds": 0.5,
            "timings": [],
        },
    )
    return AuditReport(**{**base, **overrides})


def test_a_finding_is_enveloped_with_its_producer():
    assert _report().findings[0].producer_id == "dataset_anomalies"


def test_bare_finding_without_producer_is_refused():
    with pytest.raises(ValidationError):
        _report(findings=[_finding()])


def test_ingestion_ref_and_generated_at_are_required():
    with pytest.raises(ValidationError):
        _report(ingestion_ref=None)
    with pytest.raises(ValidationError):
        _report(generated_at=None)


def test_unknown_schema_version_is_refused():
    with pytest.raises(ValidationError):
        _report(schema_version=99)


def test_unknown_fingerprint_version_is_refused():
    with pytest.raises(ValidationError):
        _report(fingerprint_version=99)


def test_report_support_types_are_exported_from_the_audit_package():
    from science_model.audit import (
        MAX_REPORT_FINDINGS,
        ProducerMetrics,
        ReportMeta,
        ReportTotals,
        UnwiredProducer,
    )

    assert MAX_REPORT_FINDINGS == 5000
    assert [
        ProducerMetrics.__name__,
        UnwiredProducer.__name__,
        ReportTotals.__name__,
        ReportMeta.__name__,
    ] == [
        "ProducerMetrics",
        "UnwiredProducer",
        "ReportTotals",
        "ReportMeta",
    ]


def test_the_report_does_not_try_to_dedup_by_identity():
    # Identity is a fingerprint over the rule's DECLARED identity qualifiers, which
    # this module cannot compute -- it does not know the registry. Enforcing the
    # one-per-(producer, finding_id) rule here would have to key on the whole payload,
    # which passes two observations with identical identity and different prose.
    # Ingestion enforces it instead; see test_findings_ingest.py.
    dup = ReportedFinding(producer_id="p", finding=_finding())
    report = _report(
        findings=[dup, dup],
        totals={
            "findings_total": 2,
            "findings_by_severity": {"warn": 2},
            "accepted_total": 0,
            "unwired_total": 0,
        },
        meta={
            "producers_run": ["p"],
            "total_duration_seconds": 0.5,
            "timings": [],
        },
    )
    assert len(report.findings) == 2


def test_two_producers_may_emit_the_same_finding():
    finding = _finding()
    report = _report(
        findings=[
            ReportedFinding(producer_id="p1", finding=finding),
            ReportedFinding(producer_id="p2", finding=finding),
        ],
        totals={
            "findings_total": 2,
            "findings_by_severity": {"warn": 2},
            "accepted_total": 0,
            "unwired_total": 0,
        },
        meta={
            "producers_run": ["p1", "p2"],
            "total_duration_seconds": 0.5,
            "timings": [],
        },
    )
    assert len(report.findings) == 2


def test_accepted_findings_carry_provenance_and_an_acceptance_key():
    from science_model.audit.report import AcceptedFinding

    report = _report(
        accepted=[
            AcceptedFinding(
                producer_id="p",
                finding=_finding(),
                acceptance_key="b" * 32,
                reason="known and accepted",
            )
        ],
        totals={
            "findings_total": 1,
            "findings_by_severity": {"warn": 1},
            "accepted_total": 1,
            "unwired_total": 0,
        },
        meta={
            "producers_run": ["dataset_anomalies", "p"],
            "total_duration_seconds": 0.5,
            "timings": [],
        },
    )
    assert report.accepted[0].acceptance_key == "b" * 32


def test_totals_must_agree_with_the_channels():
    with pytest.raises(ValidationError):
        _report(
            totals={
                "findings_total": 7,
                "findings_by_severity": {"warn": 7},
                "accepted_total": 0,
                "unwired_total": 0,
            }
        )


def test_findings_by_severity_must_agree_with_the_unsuppressed_channel():
    # The scalar total is right; the breakdown is not. A check on the total alone
    # would pass this.
    with pytest.raises(ValidationError, match="findings_by_severity"):
        _report(
            totals={
                "findings_total": 1,
                "findings_by_severity": {"error": 1},
                "accepted_total": 0,
                "unwired_total": 0,
            }
        )
    with pytest.raises(ValidationError, match="findings_by_severity"):
        _report(
            totals={
                "findings_total": 1,
                "findings_by_severity": {"warn": 1, "error": 0},
                "accepted_total": 0,
                "unwired_total": 0,
            }
        )


def test_generated_at_must_be_iso_8601():
    with pytest.raises(ValidationError, match="ISO-8601"):
        _report(generated_at="last Tuesday")
    with pytest.raises(ValidationError, match="ISO-8601"):
        _report(generated_at="2026-13-45T99:00:00")


def test_the_wire_form_refuses_the_nul_the_stored_hashes_refuse():
    """The report is where these strings ENTER, so it is where they are refused.

    Ingestion copies `ingestion_ref` and `producer_id` straight onto an `Occurrence`,
    which joins them with `\\0` into an idempotency key. Refusing only at the stored
    model would let a report validate and then blow up mid-write as a `ValidationError`
    -- outside ingestion's declared `IngestError` channel, and after the walk.
    """
    with pytest.raises(ValidationError, match="NUL"):
        _report(ingestion_ref="run:a\0b")
    with pytest.raises(ValidationError, match="NUL"):
        ReportedFinding(producer_id="p\0q", finding=_finding())


def test_the_finding_ceiling_applies_across_both_channels():
    from science_model.audit.report import MAX_REPORT_FINDINGS, AcceptedFinding

    half = MAX_REPORT_FINDINGS // 2
    findings = [
        ReportedFinding(producer_id="p", finding=_finding(ref=f"dataset:{i}"))
        for i in range(half + 1)
    ]
    accepted = [
        AcceptedFinding(
            producer_id="p",
            finding=_finding(ref=f"dataset:acc-{i}"),
            acceptance_key="b" * 32,
            reason="known",
        )
        for i in range(half + 1)
    ]
    with pytest.raises(ValidationError, match="ceiling"):
        _report(
            findings=findings,
            accepted=accepted,
            totals={
                "findings_total": len(findings),
                "findings_by_severity": {"warn": len(findings)},
                "accepted_total": len(accepted),
                "unwired_total": 0,
            },
        )


@pytest.mark.parametrize("producers_run", [[" "], ["p", "p"]])
def test_producers_run_is_nonblank_and_unique(producers_run):
    with pytest.raises(ValidationError, match="producers_run"):
        _report(
            findings=[],
            totals={
                "findings_total": 0,
                "findings_by_severity": {},
                "accepted_total": 0,
                "unwired_total": 0,
            },
            meta={
                "producers_run": producers_run,
                "total_duration_seconds": 0.5,
                "timings": [],
            },
        )


def test_successful_and_unwired_producer_sets_are_disjoint_and_unique():
    unwired = UnwiredProducer(producer_id="dataset_anomalies", code="not-wired")
    with pytest.raises(ValidationError, match="both producers_run and unwired"):
        _report(
            unwired=[unwired],
            totals={
                "findings_total": 1,
                "findings_by_severity": {"warn": 1},
                "accepted_total": 0,
                "unwired_total": 1,
            },
        )
    with pytest.raises(ValidationError, match="duplicate unwired"):
        _report(
            findings=[],
            unwired=[unwired, unwired],
            totals={
                "findings_total": 0,
                "findings_by_severity": {},
                "accepted_total": 0,
                "unwired_total": 2,
            },
            meta={
                "producers_run": ["other"],
                "total_duration_seconds": 0.5,
                "timings": [],
            },
        )


@pytest.mark.parametrize("channel", ["findings", "accepted", "metrics"])
def test_every_output_producer_is_named_in_producers_run(channel):
    overrides = {}
    if channel == "findings":
        overrides["findings"] = [
            ReportedFinding(producer_id="other", finding=_finding())
        ]
    elif channel == "accepted":
        overrides["accepted"] = [
            AcceptedFinding(
                producer_id="other",
                finding=_finding(),
                acceptance_key="b" * 32,
                reason="known",
            )
        ]
        overrides["totals"] = {
            "findings_total": 1,
            "findings_by_severity": {"warn": 1},
            "accepted_total": 1,
            "unwired_total": 0,
        }
    else:
        overrides["metrics"] = {"other": ProducerMetrics(scanned=1)}

    with pytest.raises(ValidationError, match="producers_run"):
        _report(**overrides)


def test_a_successfully_run_producer_may_emit_no_output():
    report = _report(
        findings=[],
        totals={
            "findings_total": 0,
            "findings_by_severity": {},
            "accepted_total": 0,
            "unwired_total": 0,
        },
    )
    assert tuple(report.meta.producers_run) == ("dataset_anomalies",)


def test_report_nested_collections_are_copied_and_materially_immutable():
    findings = [ReportedFinding(producer_id="dataset_anomalies", finding=_finding())]
    accepted = []
    metrics = {
        "dataset_anomalies": ProducerMetrics(
            scanned=1,
            nested={"counts": [1, 2]},
        )
    }
    unwired = []
    severities = {"warn": 1}
    producers_run = ["dataset_anomalies"]
    timings = [{"producer_id": "dataset_anomalies", "seconds": 0.1}]

    report = _report(
        findings=findings,
        accepted=accepted,
        metrics=metrics,
        unwired=unwired,
        totals={
            "findings_total": 1,
            "findings_by_severity": severities,
            "accepted_total": 0,
            "unwired_total": 0,
        },
        meta={
            "producers_run": producers_run,
            "total_duration_seconds": 0.5,
            "timings": timings,
        },
    )

    original_finding = findings[0]
    findings.clear()
    metrics.clear()
    severities["warn"] = 99
    producers_run.clear()
    timings[0]["seconds"] = 99

    assert len(report.findings) == 1
    assert report.totals.findings_by_severity == {"warn": 1}
    assert tuple(report.meta.producers_run) == ("dataset_anomalies",)
    assert report.meta.timings[0]["seconds"] == 0.1
    assert report.metrics["dataset_anomalies"].model_dump(mode="json") == {
        "scanned": 1,
        "nested": {"counts": [1, 2]},
    }

    with pytest.raises(AttributeError):
        report.findings.append(original_finding)  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        report.metrics["other"] = ProducerMetrics(scanned=2)  # type: ignore[index]
    with pytest.raises(TypeError):
        report.totals.findings_by_severity["warn"] = 99
    with pytest.raises(TypeError):
        report.meta.timings[0]["seconds"] = 99
    with pytest.raises(TypeError):
        report.metrics["dataset_anomalies"].nested["counts"][0] = 99

    dumped = report.model_dump(mode="json")
    assert type(dumped["findings"]) is list
    assert type(dumped["accepted"]) is list
    assert type(dumped["unwired"]) is list
    assert type(dumped["meta"]["producers_run"]) is list
    assert type(dumped["meta"]["timings"]) is list
    assert type(dumped["metrics"]) is dict
