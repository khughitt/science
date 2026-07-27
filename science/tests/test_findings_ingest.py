import json
from collections import Counter

import pytest
from pydantic import BaseModel, ConfigDict
from science_model.audit import (
    AuditFinding,
    AuditReport,
    EntitySubject,
    FindingRule,
    FindingSection,
    ReportedFinding,
)

from science_tool.findings.ingest import IngestError, ingest_report, load_report
from science_tool.findings.producers import FindingProducer, build_registry
from science_tool.findings.storage import load_cases


class Q(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = ""
    #: Declared on the schema but deliberately absent from `RULE.identity_qualifiers`.
    #: This is the non-identity qualifier the collision and survival tests turn on; a
    #: qualifier the schema rejects would fail validation before identity ever matters.
    note: str = ""
    #: An INT field, so the strict-validation test has a type lax mode would coerce.
    #: `str` is the wrong probe: pydantic's lax mode already refuses an int for a
    #: `str` field, so `field=1` would fail either way and prove nothing.
    count: int = 0


SECTION = FindingSection(id="datasets", title="Datasets", section_order=300)
RULE = FindingRule(
    id="dataset.stale-review",
    severities={"warn"},
    subject_types={"entity"},
    qualifier_schema=Q,
    identity_qualifiers=("field",),
    title="t",
    section="datasets",
    display_order=100,
)
REGISTRY = build_registry(
    [
        FindingProducer(
            producer_id="dataset_anomalies",
            namespace="health_checks",
            rules=(RULE,),
            sections=(SECTION,),
            metrics_schema=None,
            remediators=frozenset(),
        )
    ]
)


def _finding(**overrides) -> AuditFinding:
    base = dict(
        rule_id="dataset.stale-review",
        subject=EntitySubject(ref="dataset:a"),
        severity="warn",
        qualifiers={"field": "year"},
        message="stale",
        evidence=[],
    )
    return AuditFinding(**{**base, **overrides})


def _report(findings=None, accepted=None, **overrides) -> AuditReport:
    findings = (
        findings
        if findings is not None
        else [ReportedFinding(producer_id="dataset_anomalies", finding=_finding())]
    )
    accepted = accepted or []
    # `findings_by_severity` is DERIVED here, not hardcoded: `AuditReport` now checks
    # the breakdown against the channel, so a helper that always says `warn` would make
    # every non-warn test fail at construction instead of where it means to.
    base = dict(
        schema_version=2,
        fingerprint_version=1,
        ingestion_ref="ing:1",
        generated_at="2026-07-27T12:00:00+00:00",
        findings=findings,
        accepted=accepted,
        metrics={},
        unwired=[],
        totals={
            "findings_total": len(findings),
            "findings_by_severity": dict(
                Counter(item.finding.severity for item in findings)
            ),
            "accepted_total": len(accepted),
            "unwired_total": 0,
        },
        meta={
            "producers_run": ["dataset_anomalies"],
            "total_duration_seconds": 0.1,
            "timings": [],
        },
    )
    return AuditReport(**{**base, **overrides})


def test_ingest_writes_a_case_with_a_genesis_transition(tmp_path):
    outcome = ingest_report(tmp_path, _report(), REGISTRY)
    assert outcome.records_written == 1
    record = load_cases(tmp_path)[0]
    assert record.status == "proposed"
    assert record.transitions[0].from_status is None
    assert len(record.occurrences) == 1


def test_reingesting_an_identical_report_appends_nothing(tmp_path):
    ingest_report(tmp_path, _report(), REGISTRY)
    second = ingest_report(tmp_path, _report(), REGISTRY)
    assert second.occurrences_appended == 0
    assert second.occurrences_skipped == 1
    assert len(load_cases(tmp_path)[0].occurrences) == 1


def test_a_later_ingestion_ref_appends_a_second_occurrence(tmp_path):
    ingest_report(tmp_path, _report(), REGISTRY)
    ingest_report(tmp_path, _report(ingestion_ref="ing:2"), REGISTRY)
    assert len(load_cases(tmp_path)[0].occurrences) == 2


def test_same_key_with_different_content_is_an_error_not_a_retry(tmp_path):
    ingest_report(tmp_path, _report(), REGISTRY)
    conflicting = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(message="DIFFERENT"),
            )
        ]
    )
    with pytest.raises(IngestError, match="idempotency"):
        ingest_report(tmp_path, conflicting, REGISTRY)


def test_reusing_an_ingestion_ref_with_a_NEW_TIMESTAMP_is_a_conflict(tmp_path):
    # Same run identifier claiming a different moment. The idempotency key is derived
    # from (producer, ingestion_ref, finding_id) and so is unchanged -- only the
    # content comparison can catch this, and only if it includes `observed_at`.
    ingest_report(tmp_path, _report(), REGISTRY)
    with pytest.raises(IngestError, match="idempotency"):
        ingest_report(
            tmp_path,
            _report(generated_at="2026-07-27T18:30:00+00:00"),
            REGISTRY,
        )
    assert len(load_cases(tmp_path)[0].occurrences) == 1


def test_the_same_instant_spelled_differently_is_still_a_retry(tmp_path):
    # 13:30+01:00 IS 12:30Z. Normalizing the instant is what keeps the check above
    # from firing on a mere change of timezone spelling.
    ingest_report(
        tmp_path,
        _report(generated_at="2026-07-27T12:30:00+00:00"),
        REGISTRY,
    )
    outcome = ingest_report(
        tmp_path,
        _report(generated_at="2026-07-27T13:30:00+01:00"),
        REGISTRY,
    )
    assert outcome.occurrences_skipped == 1
    assert outcome.occurrences_appended == 0


def test_two_producers_upsert_one_record_with_two_occurrences(tmp_path):
    registry = build_registry(
        [
            FindingProducer(
                producer_id="dataset_anomalies",
                namespace="health_checks",
                rules=(RULE,),
                sections=(SECTION,),
                metrics_schema=None,
                remediators=frozenset(),
            ),
            FindingProducer(
                producer_id="curation_lens",
                namespace="health_checks",
                rules=(),
                sections=(),
                metrics_schema=None,
                remediators=frozenset(),
            ),
        ]
    )
    report = _report(
        findings=[
            ReportedFinding(producer_id="dataset_anomalies", finding=_finding()),
            ReportedFinding(producer_id="curation_lens", finding=_finding()),
        ]
    )
    ingest_report(tmp_path, report, registry)
    records = load_cases(tmp_path)
    assert len(records) == 1
    assert {o.producer_id for o in records[0].occurrences} == {
        "dataset_anomalies",
        "curation_lens",
    }


def _normalized(record) -> dict:
    """The COMPLETE record, with history sorted so the comparison is order-insensitive
    without being blind: any field differing anywhere still fails."""
    payload = record.model_dump(mode="json")
    payload["occurrences"] = sorted(
        payload["occurrences"], key=lambda o: o["idempotency_key"]
    )
    payload["reviews"] = sorted(payload["reviews"], key=lambda r: r["review_id"])
    return payload


def test_no_arrival_order_dependence(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    first = _report(
        findings=[ReportedFinding(producer_id="dataset_anomalies", finding=_finding())]
    )
    second = _report(
        ingestion_ref="ing:2",
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(message="later"),
            )
        ],
    )
    ingest_report(a, first, REGISTRY)
    ingest_report(a, second, REGISTRY)
    ingest_report(b, second, REGISTRY)
    ingest_report(b, first, REGISTRY)
    # Compare the WHOLE record. Matching only finding ids and occurrence keys would
    # pass even if the two orders produced different statuses, transitions, severities,
    # or messages -- which is the entire class of thing this test is about.
    assert _normalized(load_cases(a)[0]) == _normalized(load_cases(b)[0])


def test_no_arrival_order_dependence_with_distinct_times_and_producers(tmp_path):
    registry = build_registry(
        [
            FindingProducer(
                producer_id="dataset_anomalies",
                namespace="health_checks",
                rules=(RULE,),
                sections=(SECTION,),
                metrics_schema=None,
                remediators=frozenset(),
            ),
            FindingProducer(
                producer_id="curation_lens",
                namespace="health_checks",
                rules=(),
                sections=(),
                metrics_schema=None,
                remediators=frozenset(),
            ),
        ]
    )
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    early = _report(
        ingestion_ref="ing:early",
        generated_at="2026-07-27T10:00:00+00:00",
        findings=[
            ReportedFinding(producer_id="curation_lens", finding=_finding())
        ],
    )
    late = _report(
        ingestion_ref="ing:late",
        generated_at="2026-07-27T14:00:00+00:00",
        findings=[
            ReportedFinding(producer_id="dataset_anomalies", finding=_finding())
        ],
    )

    ingest_report(a, early, registry)
    ingest_report(a, late, registry)
    ingest_report(b, late, registry)
    ingest_report(b, early, registry)

    first = load_cases(a)[0]
    second = load_cases(b)[0]
    assert _normalized(first) == _normalized(second)
    assert first.transitions[0].at.isoformat() == "2026-07-27T10:00:00+00:00"
    assert first.transitions[0].reason == "detected by curation_lens"
    assert [
        (occurrence.observed_at, occurrence.idempotency_key)
        for occurrence in first.occurrences
    ] == sorted(
        (occurrence.observed_at, occurrence.idempotency_key)
        for occurrence in first.occurrences
    )


def test_non_identity_qualifiers_survive_on_the_occurrence(tmp_path):
    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(qualifiers={"field": "year", "note": "extra"}),
            )
        ]
    )
    ingest_report(tmp_path, report, REGISTRY)
    record = load_cases(tmp_path)[0]
    assert set(record.occurrences[0].qualifiers) == {"field", "note"}
    assert set(record.identity_qualifiers) == {"field"}


def test_accepted_observations_are_ingested_and_leave_status_alone(tmp_path):
    from science_model.audit import AcceptedFinding

    report = _report(
        findings=[],
        accepted=[
            AcceptedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(),
                acceptance_key="b" * 32,
                reason="known",
            )
        ],
    )
    ingest_report(tmp_path, report, REGISTRY)
    record = load_cases(tmp_path)[0]
    assert record.status == "proposed"
    assert record.occurrences[0].acceptance_key == "b" * 32


def test_the_same_observation_accepted_and_unsuppressed_conflicts(tmp_path):
    from science_model.audit import AcceptedFinding

    ingest_report(tmp_path, _report(), REGISTRY)
    with pytest.raises(IngestError, match="idempotency"):
        ingest_report(
            tmp_path,
            _report(
                findings=[],
                accepted=[
                    AcceptedFinding(
                        producer_id="dataset_anomalies",
                        finding=_finding(),
                        acceptance_key="b" * 32,
                        reason="known",
                    )
                ],
            ),
            REGISTRY,
        )


def test_an_omitted_identity_qualifier_is_refused_despite_the_schemas_default(
    tmp_path,
):
    # `Q.field` has a default, so `{}` passes schema validation and reports `field=""`.
    # The fingerprint would nonetheless be computed over `{}`, giving this observation
    # a different identity from an otherwise identical one that stated `field: ""`.
    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(qualifiers={}),
            )
        ]
    )
    with pytest.raises(IngestError, match="declared but absent"):
        ingest_report(tmp_path, report, REGISTRY)
    assert load_cases(tmp_path) == []


def test_a_wrongly_typed_qualifier_is_refused_at_the_write_boundary(tmp_path):
    """The producer boundary and the write boundary run the SAME strict routine.

    A report is untrusted input: nothing guarantees it came from `FindingRule.build()`.
    Lax validation here would accept `"3"` for `count: int`, report `3`, discard that
    model, and store the string -- so `3` and `"3"` would be two spellings of one
    observation, both valid. Nothing is written.
    """
    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(qualifiers={"field": "year", "count": "3"}),
            )
        ]
    )
    with pytest.raises(IngestError, match="qualifiers invalid"):
        ingest_report(tmp_path, report, REGISTRY)
    assert load_cases(tmp_path) == []

    # The well-typed spelling of the same observation is accepted.
    ok = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(qualifiers={"field": "year", "count": 3}),
            )
        ]
    )
    assert ingest_report(tmp_path, ok, REGISTRY).records_written == 1


def test_an_undeclared_rule_is_refused(tmp_path):
    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(rule_id="dataset.never-declared"),
            )
        ]
    )
    with pytest.raises(IngestError, match="undeclared rule"):
        ingest_report(tmp_path, report, REGISTRY)


def test_an_unregistered_producer_is_refused(tmp_path):
    report = _report(
        findings=[ReportedFinding(producer_id="who", finding=_finding())]
    )
    with pytest.raises(IngestError, match="unregistered producer"):
        ingest_report(tmp_path, report, REGISTRY)


def test_a_severity_outside_the_rule_is_refused(tmp_path):
    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(severity="error"),
            )
        ]
    )
    with pytest.raises(IngestError, match="severity"):
        ingest_report(tmp_path, report, REGISTRY)


def test_a_validation_failure_writes_nothing(tmp_path):
    # The first finding is valid, the second names an undeclared rule. Prevalidation
    # must reject the whole report before the first one reaches disk.
    valid = ReportedFinding(producer_id="dataset_anomalies", finding=_finding())
    invalid = ReportedFinding(
        producer_id="dataset_anomalies",
        finding=_finding(
            subject=EntitySubject(ref="dataset:b"),
            rule_id="dataset.never-declared",
        ),
    )
    with pytest.raises(IngestError):
        ingest_report(tmp_path, _report(findings=[valid, invalid]), REGISTRY)
    assert load_cases(tmp_path) == []


def _assert_forged_report_is_refused_without_mutation(tmp_path, report) -> None:
    with pytest.raises(IngestError, match="not a valid audit report"):
        ingest_report(tmp_path, report, REGISTRY)
    assert not (tmp_path / "doc").exists()


def test_ingest_revalidates_a_model_copy_with_a_forged_schema_version(tmp_path):
    forged = _report().model_copy(update={"schema_version": 99})

    _assert_forged_report_is_refused_without_mutation(tmp_path, forged)


def test_ingest_revalidates_a_model_copy_with_forged_totals(tmp_path):
    report = _report()
    forged_totals = report.totals.model_copy(update={"findings_total": 0})
    forged = report.model_copy(update={"totals": forged_totals})

    _assert_forged_report_is_refused_without_mutation(tmp_path, forged)


def test_ingest_revalidates_a_forged_report_count(tmp_path):
    report = _report()
    forged = report.model_copy(update={"findings": report.findings * 5001})

    _assert_forged_report_is_refused_without_mutation(tmp_path, forged)


def test_ingest_revalidates_nested_values_from_model_construct(tmp_path):
    report = _report()
    raw_finding = _finding().model_dump(mode="python")
    raw_finding["severity"] = 7
    forged_envelope = ReportedFinding.model_construct(
        producer_id="dataset_anomalies",
        finding=raw_finding,
    )
    raw_report = report.model_dump(mode="python")
    raw_report["findings"] = [forged_envelope]
    forged = AuditReport.model_construct(**raw_report)

    _assert_forged_report_is_refused_without_mutation(tmp_path, forged)


def test_ingest_snapshots_and_revalidates_mutable_report_lists(tmp_path):
    report = _report()
    findings_alias = report.findings
    findings_alias.append(
        ReportedFinding(
            producer_id="dataset_anomalies",
            finding=_finding(subject=EntitySubject(ref="dataset:b")),
        )
    )

    _assert_forged_report_is_refused_without_mutation(tmp_path, report)


def test_partial_failure_is_repaired_by_rerunning_the_same_report(tmp_path):
    # Simulate a crash after the first of two records is written, by writing the
    # first record alone and then re-ingesting the whole report.
    first_only = _report(
        findings=[ReportedFinding(producer_id="dataset_anomalies", finding=_finding())]
    )
    ingest_report(tmp_path, first_only, REGISTRY)
    both = _report(
        findings=[
            ReportedFinding(producer_id="dataset_anomalies", finding=_finding()),
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(subject=EntitySubject(ref="dataset:b")),
            ),
        ]
    )
    outcome = ingest_report(tmp_path, both, REGISTRY)
    assert outcome.occurrences_skipped == 1
    assert len(load_cases(tmp_path)) == 2
    for record in load_cases(tmp_path):
        assert len(record.occurrences) == 1


def test_a_late_idempotency_conflict_writes_no_earlier_new_case(tmp_path):
    ingest_report(tmp_path, _report(), REGISTRY)
    new_then_conflicting = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(subject=EntitySubject(ref="dataset:b")),
            ),
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(message="DIFFERENT"),
            ),
        ]
    )

    with pytest.raises(IngestError, match="idempotency"):
        ingest_report(tmp_path, new_then_conflicting, REGISTRY)

    records = load_cases(tmp_path)
    assert len(records) == 1
    assert records[0].subject == EntitySubject(ref="dataset:a")


def test_load_report_refuses_an_unknown_schema_version(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    with pytest.raises(IngestError, match="schema_version"):
        load_report(tmp_path, path)


def test_load_report_wraps_an_oversized_integer_parse_error(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(
        '{"schema_version": 2, "value": ' + ("9" * 5000) + "}",
        encoding="utf-8",
    )

    with pytest.raises(IngestError, match="could not parse"):
        load_report(tmp_path, path)


def test_load_report_wraps_a_deep_nesting_parse_error(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(("[" * 10000) + "0" + ("]" * 10000), encoding="utf-8")

    with pytest.raises(IngestError, match="could not parse"):
        load_report(tmp_path, path)


def test_load_report_refuses_an_oversize_report(tmp_path):
    from science_tool.findings.ingest import MAX_REPORT_BYTES

    path = tmp_path / "report.json"
    path.write_text("x" * (MAX_REPORT_BYTES + 1), encoding="utf-8")
    with pytest.raises(IngestError, match="exceeds"):
        load_report(tmp_path, path)


def test_load_report_refuses_a_symlinked_report(tmp_path):
    real = tmp_path / "real.json"
    real.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(IngestError, match="symlink"):
        load_report(tmp_path, link)


def test_load_report_refuses_a_report_under_a_symlinked_PARENT(tmp_path):
    # The report file itself is real; `runs/` is the link. An `O_NOFOLLOW` on the
    # final component alone reads this without complaint.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "report.json").write_text("{}", encoding="utf-8")
    (tmp_path / "runs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(IngestError, match="symlink"):
        load_report(tmp_path, tmp_path / "runs" / "report.json")


def test_load_report_refuses_a_report_outside_the_project(tmp_path):
    # §8 gives the actor ONE supervisor-supplied report path, on a surface the
    # `report-only` tier already allows -- which is inside the project.
    project = tmp_path / "project"
    project.mkdir()
    stray = tmp_path / "stray.json"
    stray.write_text("{}", encoding="utf-8")
    with pytest.raises(IngestError, match="outside the project root"):
        load_report(project, stray)


def test_a_dangling_case_symlink_is_refused_rather_than_overwritten(tmp_path):
    # `Path.exists()` is False for a dangling link, so an existence check would treat
    # this as "no case yet" and write straight through the link.
    from science_tool.findings.storage import case_path

    ingest_report(tmp_path, _report(), REGISTRY)
    records = load_cases(tmp_path)
    path = case_path(tmp_path, records[0])
    path.unlink()
    path.symlink_to(tmp_path / "gone.md")
    with pytest.raises(IngestError, match="symlink"):
        ingest_report(tmp_path, _report(ingestion_ref="ing:2"), REGISTRY)


def test_evidence_path_escaping_the_project_is_refused_at_the_model(tmp_path):
    from pydantic import ValidationError
    from science_model.audit import LocationEvidence

    with pytest.raises(ValidationError):
        LocationEvidence(path="../../etc/passwd")


def test_one_producer_emitting_two_findings_with_one_identity_is_refused(tmp_path):
    # Same rule, same subject, same identity qualifiers -- different prose. The model
    # cannot catch this (it does not know which qualifiers bear identity); ingestion
    # must, or the collision surfaces later as an idempotency conflict.
    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(message="first"),
            ),
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(message="second"),
            ),
        ]
    )
    with pytest.raises(IngestError, match="two findings with identity"):
        ingest_report(tmp_path, report, REGISTRY)
    assert load_cases(tmp_path) == []


def test_a_non_identity_qualifier_difference_still_collides(tmp_path):
    # The two payloads differ ONLY in `note`, which `RULE` does not list among its
    # identity qualifiers, so they share a fingerprint and collide. A version of this
    # test where both payloads carry the same qualifiers proves nothing about
    # non-identity qualifiers -- it is just the previous test again.
    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(
                    qualifiers={"field": "year", "note": "first look"}
                ),
            ),
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(
                    qualifiers={"field": "year", "note": "second look"}
                ),
            ),
        ]
    )
    with pytest.raises(IngestError, match="two findings with identity"):
        ingest_report(tmp_path, report, REGISTRY)


def test_a_subject_path_through_a_symlink_is_refused(tmp_path):
    from science_model.audit import PathSubject

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.md").write_text("hi", encoding="utf-8")
    (tmp_path / "doc").symlink_to(outside, target_is_directory=True)

    path_rule = FindingRule(
        id="tags.lingering",
        severities={"warn"},
        subject_types={"path"},
        qualifier_schema=Q,
        title="t",
        section="datasets",
        display_order=110,
    )
    registry = build_registry(
        [
            FindingProducer(
                producer_id="dataset_anomalies",
                namespace="health_checks",
                rules=(RULE, path_rule),
                sections=(SECTION,),
                metrics_schema=None,
                remediators=frozenset(),
            )
        ]
    )
    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=AuditFinding(
                    rule_id="tags.lingering",
                    subject=PathSubject(path="doc/x.md"),
                    severity="warn",
                    qualifiers={},
                    message="m",
                    evidence=[],
                ),
            )
        ]
    )
    with pytest.raises(IngestError, match="symlink"):
        ingest_report(tmp_path, report, registry)


def test_an_evidence_path_through_a_symlink_is_refused(tmp_path):
    from science_model.audit import LocationEvidence

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.md").write_text("hi", encoding="utf-8")
    (tmp_path / "doc").symlink_to(outside, target_is_directory=True)

    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(
                    evidence=[LocationEvidence(path="doc/x.md", line=1)]
                ),
            )
        ]
    )
    with pytest.raises(IngestError, match="symlink"):
        ingest_report(tmp_path, report, REGISTRY)


def test_a_symlinked_lock_file_is_refused(tmp_path):
    cases = tmp_path / "doc" / "audits" / "cases"
    cases.mkdir(parents=True)
    outside = tmp_path / "outside.lock"
    outside.write_text("", encoding="utf-8")
    (cases / ".ingest.lock").symlink_to(outside)
    with pytest.raises(IngestError, match="symlink|link"):
        ingest_report(tmp_path, _report(), REGISTRY)
