import json
import inspect
from collections import Counter

import pytest
from pydantic import BaseModel, ConfigDict, Field
from science_model.audit import (
    AcceptedFinding,
    AuditFinding,
    AuditReport,
    EntitySubject,
    FindingRule,
    FindingSection,
    ReportedFinding,
    finding_fingerprint,
)

from science_tool.findings.ingest import (
    IngestError,
    IngestionContext,
    IngestionProvenance,
    ingest_report as _ingest_report,
    load_report,
)
from science_tool.findings.producers import FindingProducer, build_registry
from science_tool.findings.storage import CASES_DIRNAME, MAX_CASE_BYTES, load_cases
from science_tool.graph.errors import EntityIdentityCollisionError


class Q(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = ""
    #: Declared on the schema but deliberately absent from `RULE.identity_qualifiers`.
    #: This is the non-identity qualifier the collision and survival tests turn on; a
    #: qualifier the schema rejects would fail validation before identity ever matters.
    note: str | None = ""
    #: An INT field, so the strict-validation test has a type lax mode would coerce.
    #: `str` is the wrong probe: pydantic's lax mode already refuses an int for a
    #: `str` field, so `field=1` would fail either way and prove nothing.
    count: int = 0


class ListQ(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tags: list[str]


class TupleQ(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tags: tuple[str, ...]


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
LIST_RULE = FindingRule(
    id="dataset.tag-sequence",
    severities={"warn"},
    subject_types={"entity"},
    qualifier_schema=ListQ,
    identity_qualifiers=("tags",),
    title="t",
    section="datasets",
    display_order=101,
)
TUPLE_RULE = FindingRule(
    id="dataset.tag-tuple",
    severities={"warn"},
    subject_types={"entity"},
    qualifier_schema=TupleQ,
    identity_qualifiers=("tags",),
    title="t",
    section="datasets",
    display_order=102,
)
REGISTRY = build_registry(
    [
        FindingProducer(
            producer_id="dataset_anomalies",
            namespace="health_checks",
            source_module="graph/health_checks/test.py",
            rules=(RULE,),
            sections=(SECTION,),
            metrics_schema=None,
            remediators=frozenset(),
        )
    ],
    active_kinds=frozenset(),
)


def _seed_entity(project_root, ref):
    prefix, _, slug = ref.partition(":")
    homes = {
        "dataset": "datasets",
        "hypothesis": "hypotheses",
    }
    path = project_root / "entities" / homes[prefix] / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: {ref}\nkind: {prefix}\ntitle: {slug}\n---\n",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _canonical_entity_fixture(tmp_path):
    _seed_entity(tmp_path, "dataset:a")
    _seed_entity(tmp_path, "dataset:b")


@pytest.mark.parametrize(
    "array_rule",
    [pytest.param(LIST_RULE, id="list"), pytest.param(TUPLE_RULE, id="tuple")],
)
def test_array_identity_qualifier_round_trips_from_build_through_ingestion(
    tmp_path,
    array_rule,
):
    registry = build_registry(
        [
            FindingProducer(
                producer_id="dataset_anomalies",
                namespace="health_checks",
                source_module="graph/health_checks/test.py",
                rules=(RULE, array_rule),
                sections=(SECTION,),
                metrics_schema=None,
                remediators=frozenset(),
            )
        ],
        active_kinds=frozenset(),
    )
    finding = array_rule.build(
        subject=EntitySubject(ref="dataset:a"),
        severity="warn",
        qualifiers={"tags": ["raw", "derived"]},
        message="ordered tags differ",
    )
    assert finding.model_dump(mode="json")["qualifiers"]["tags"] == [
        "raw",
        "derived",
    ]

    ingest_report(
        tmp_path,
        _report(
            findings=[
                ReportedFinding(
                    producer_id="dataset_anomalies",
                    finding=finding,
                )
            ]
        ),
        registry,
    )

    record = load_cases(tmp_path)[0]
    assert record.model_dump(mode="json")["identity_qualifiers"]["tags"] == [
        "raw",
        "derived",
    ]
    assert record.model_dump(mode="json")["occurrences"][0]["qualifiers"]["tags"] == [
        "raw",
        "derived",
    ]


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
        findings if findings is not None else [ReportedFinding(producer_id="dataset_anomalies", finding=_finding())]
    )
    accepted = accepted or []
    producers_run = sorted(
        {
            *(item.producer_id for item in findings),
            *(item.producer_id for item in accepted),
        }
    ) or ["dataset_anomalies"]
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
            "findings_by_severity": dict(Counter(item.finding.severity for item in findings)),
            "accepted_total": len(accepted),
            "unwired_total": 0,
        },
        meta={
            "producers_run": producers_run,
            "total_duration_seconds": 0.1,
            "timings": [],
        },
    )
    return AuditReport(**{**base, **overrides})


def _provenance(report: AuditReport) -> IngestionProvenance:
    return IngestionProvenance(
        ingestion_ref=report.ingestion_ref,
        generated_at=report.generated_at,
        producer_ids=frozenset(
            {
                *report.meta.producers_run,
                *(item.producer_id for item in report.unwired),
            }
        ),
    )


def ingest_report(
    project_root,
    report: AuditReport,
    registry,
    *,
    provenance: IngestionProvenance | None = None,
    context: IngestionContext | None = None,
    actor: str = "ingest",
):
    """Test convenience: production callers must supply both trusted inputs."""
    return _ingest_report(
        project_root,
        report,
        registry,
        provenance=provenance or _provenance(report),
        context=context or IngestionContext(canonical_entity_ids=frozenset({"dataset:a", "dataset:b"})),
        actor=actor,
    )


def test_ingest_writes_a_case_with_a_genesis_transition(tmp_path):
    outcome = ingest_report(tmp_path, _report(), REGISTRY)
    assert outcome.records_written == 1
    record = load_cases(tmp_path)[0]
    assert record.status == "proposed"
    assert record.transitions[0].from_status is None
    assert record.transitions[0].actor == "ingest"
    assert len(record.occurrences) == 1


def test_direct_ingestion_requires_both_trusted_inputs_and_defaults_actor_to_ingest():
    parameters = inspect.signature(_ingest_report).parameters
    assert parameters["provenance"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["provenance"].default is inspect.Parameter.empty
    assert parameters["context"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["context"].default is inspect.Parameter.empty
    assert parameters["actor"].default == "ingest"


@pytest.mark.parametrize(
    ("field", "provenance"),
    [
        (
            "ingestion_ref",
            IngestionProvenance(
                ingestion_ref="attested:other",
                generated_at="2026-07-27T12:00:00+00:00",
                producer_ids=frozenset({"dataset_anomalies"}),
            ),
        ),
        (
            "generated_at",
            IngestionProvenance(
                ingestion_ref="ing:1",
                generated_at="2026-07-27T12:01:00+00:00",
                producer_ids=frozenset({"dataset_anomalies"}),
            ),
        ),
        (
            "producer ids",
            IngestionProvenance(
                ingestion_ref="ing:1",
                generated_at="2026-07-27T12:00:00+00:00",
                producer_ids=frozenset({"different_producer"}),
            ),
        ),
    ],
)
def test_report_provenance_must_exactly_match_the_trusted_attestation(
    tmp_path,
    field,
    provenance,
):
    with pytest.raises(IngestError, match=field):
        _ingest_report(
            tmp_path,
            _report(),
            REGISTRY,
            provenance=provenance,
            context=IngestionContext(canonical_entity_ids=frozenset({"dataset:a"})),
        )
    assert not (tmp_path / CASES_DIRNAME).exists()


def _registry_with_second_producer():
    return build_registry(
        [
            FindingProducer(
                producer_id="dataset_anomalies",
                namespace="health_checks",
                source_module="graph/health_checks/test.py",
                rules=(RULE,),
                sections=(SECTION,),
                metrics_schema=None,
                remediators=frozenset(),
            ),
            FindingProducer(
                producer_id="curation_lens",
                namespace="health_checks",
                source_module="graph/health_checks/test.py",
                rules=(),
                sections=(),
                metrics_schema=None,
                remediators=frozenset(),
            ),
        ],
        active_kinds=frozenset(),
    )


def test_a_registered_producer_cannot_impersonate_the_attested_producer(tmp_path):
    report = _report(findings=[ReportedFinding(producer_id="curation_lens", finding=_finding())])
    provenance = IngestionProvenance(
        ingestion_ref=report.ingestion_ref,
        generated_at=report.generated_at,
        producer_ids=frozenset({"dataset_anomalies"}),
    )

    with pytest.raises(IngestError, match="producer ids"):
        _ingest_report(
            tmp_path,
            report,
            _registry_with_second_producer(),
            provenance=provenance,
            context=IngestionContext(canonical_entity_ids=frozenset({"dataset:a"})),
        )
    assert not (tmp_path / CASES_DIRNAME).exists()


@pytest.mark.parametrize(
    ("report_ids", "attested_ids"),
    [
        (
            ["dataset_anomalies"],
            frozenset({"dataset_anomalies", "curation_lens"}),
        ),
        (
            ["dataset_anomalies", "curation_lens"],
            frozenset({"dataset_anomalies"}),
        ),
    ],
    ids=["attestation-has-extra", "report-has-extra"],
)
def test_producer_attestation_set_equality_has_no_subset_fallback(
    tmp_path,
    report_ids,
    attested_ids,
):
    report = _report(
        meta={
            "producers_run": report_ids,
            "total_duration_seconds": 0.1,
            "timings": [],
        }
    )
    provenance = IngestionProvenance(
        ingestion_ref=report.ingestion_ref,
        generated_at=report.generated_at,
        producer_ids=attested_ids,
    )

    with pytest.raises(IngestError, match="producer ids"):
        _ingest_report(
            tmp_path,
            report,
            _registry_with_second_producer(),
            provenance=provenance,
            context=IngestionContext(canonical_entity_ids=frozenset({"dataset:a"})),
        )
    assert not (tmp_path / CASES_DIRNAME).exists()


def test_unwired_producers_are_part_of_the_exact_attested_set(tmp_path):
    from science_model.audit import UnwiredProducer

    report = _report(
        findings=[],
        unwired=[
            UnwiredProducer(
                producer_id="curation_lens",
                code="not-wired",
                reason="disabled",
            )
        ],
        totals={
            "findings_total": 0,
            "findings_by_severity": {},
            "accepted_total": 0,
            "unwired_total": 1,
        },
    )
    provenance = IngestionProvenance(
        ingestion_ref=report.ingestion_ref,
        generated_at=report.generated_at,
        producer_ids=frozenset({"dataset_anomalies"}),
    )

    with pytest.raises(IngestError, match="producer ids"):
        _ingest_report(
            tmp_path,
            report,
            _registry_with_second_producer(),
            provenance=provenance,
            context=IngestionContext(canonical_entity_ids=frozenset()),
        )
    assert not (tmp_path / CASES_DIRNAME).exists()


def test_an_actor_cannot_preempt_a_future_genuine_ingestion_ref(tmp_path):
    claimed = _report(ingestion_ref="run:genuine")
    current_attestation = IngestionProvenance(
        ingestion_ref="run:current",
        generated_at=claimed.generated_at,
        producer_ids=frozenset({"dataset_anomalies"}),
    )
    with pytest.raises(IngestError, match="ingestion_ref"):
        _ingest_report(
            tmp_path,
            claimed,
            REGISTRY,
            provenance=current_attestation,
            context=IngestionContext(canonical_entity_ids=frozenset({"dataset:a"})),
        )

    genuine = _report(
        ingestion_ref="run:genuine",
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(message="genuine observation"),
            )
        ],
    )
    outcome = _ingest_report(
        tmp_path,
        genuine,
        REGISTRY,
        provenance=_provenance(genuine),
        context=IngestionContext(canonical_entity_ids=frozenset({"dataset:a"})),
    )

    assert outcome.records_written == 1
    assert load_cases(tmp_path)[0].occurrences[0].message == "genuine observation"


def test_report_cannot_expand_the_trusted_canonical_entity_universe(tmp_path):
    report = _report()
    with pytest.raises(IngestError, match="trusted canonical"):
        _ingest_report(
            tmp_path,
            report,
            REGISTRY,
            provenance=_provenance(report),
            context=IngestionContext(canonical_entity_ids=frozenset()),
        )
    assert not (tmp_path / CASES_DIRNAME).exists()


def test_graph_context_accepts_an_adapter_backed_entity(tmp_path):
    from science_tool.findings.cli import _load_ingestion_context

    papers = tmp_path / "papers"
    papers.mkdir()
    papers.joinpath("references.bib").write_text(
        "@article{Smith2024,\n  title = {Cells},\n  year = {2024},\n}\n",
        encoding="utf-8",
    )
    context, _entity_registry = _load_ingestion_context(tmp_path)
    assert "paper:Smith2024" in context.canonical_entity_ids
    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(subject=EntitySubject(ref="paper:Smith2024")),
            )
        ]
    )

    outcome = _ingest_report(
        tmp_path,
        report,
        REGISTRY,
        provenance=_provenance(report),
        context=context,
    )

    assert outcome.records_written == 1


def test_graph_context_refuses_duplicate_owners_before_ingestion(tmp_path):
    from science_tool.findings.cli import _load_ingestion_context

    for name in ("q1.md", "q1-duplicate.md"):
        path = tmp_path / "entities" / "questions" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\nid: question:q1\nkind: question\ntitle: Q1\n---\n",
            encoding="utf-8",
        )

    with pytest.raises(EntityIdentityCollisionError, match="question:q1"):
        _load_ingestion_context(tmp_path)
    assert not (tmp_path / CASES_DIRNAME).exists()


def test_graph_invalid_entities_do_not_enter_the_trusted_context(tmp_path):
    from science_tool.findings.cli import _load_ingestion_context

    invalid = tmp_path / "entities" / "reports" / "invalid.md"
    invalid.parent.mkdir(parents=True)
    invalid.write_text(
        "---\nid: mystery:invalid\nkind: mystery\ntitle: Invalid\n---\n",
        encoding="utf-8",
    )
    context, _entity_registry = _load_ingestion_context(tmp_path)
    assert "mystery:invalid" not in context.canonical_entity_ids
    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(subject=EntitySubject(ref="mystery:invalid")),
            )
        ]
    )

    with pytest.raises(IngestError, match="trusted canonical"):
        _ingest_report(
            tmp_path,
            report,
            REGISTRY,
            provenance=_provenance(report),
            context=context,
        )
    assert not (tmp_path / CASES_DIRNAME).exists()


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


@pytest.mark.parametrize(
    ("first_qualifiers", "retry_qualifiers"),
    [
        ({"field": "year"}, {"field": "year", "note": None}),
        ({"field": "year", "note": None}, {"field": "year"}),
    ],
)
def test_absent_and_explicit_null_qualifiers_are_an_idempotency_conflict(
    tmp_path,
    first_qualifiers,
    retry_qualifiers,
):
    first = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(qualifiers=first_qualifiers),
            )
        ]
    )
    retry = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(qualifiers=retry_qualifiers),
            )
        ]
    )

    ingest_report(tmp_path, first, REGISTRY)
    with pytest.raises(IngestError, match="idempotency"):
        ingest_report(tmp_path, retry, REGISTRY)

    assert len(load_cases(tmp_path)[0].occurrences) == 1


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
                source_module="graph/health_checks/test.py",
                rules=(RULE,),
                sections=(SECTION,),
                metrics_schema=None,
                remediators=frozenset(),
            ),
            FindingProducer(
                producer_id="curation_lens",
                namespace="health_checks",
                source_module="graph/health_checks/test.py",
                rules=(),
                sections=(),
                metrics_schema=None,
                remediators=frozenset(),
            ),
        ],
        active_kinds=frozenset(),
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


def _canonical_state(record) -> dict:
    """Arrival-invariant state, deliberately excluding creation history."""
    payload = record.model_dump(mode="json")
    return {
        "finding_id": payload["finding_id"],
        "fingerprint_version": payload["fingerprint_version"],
        "rule_id": payload["rule_id"],
        "subject": payload["subject"],
        "identity_qualifiers": payload["identity_qualifiers"],
        "occurrences": payload["occurrences"],
        "current_severity": record.current_severity(),
    }


def test_no_arrival_order_dependence(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _seed_entity(a, "dataset:a")
    _seed_entity(b, "dataset:a")
    first = _report(findings=[ReportedFinding(producer_id="dataset_anomalies", finding=_finding())])
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
    assert _canonical_state(load_cases(a)[0]) == _canonical_state(load_cases(b)[0])


def test_no_arrival_order_dependence_with_distinct_times_and_producers(tmp_path):
    registry = build_registry(
        [
            FindingProducer(
                producer_id="dataset_anomalies",
                namespace="health_checks",
                source_module="graph/health_checks/test.py",
                rules=(RULE,),
                sections=(SECTION,),
                metrics_schema=None,
                remediators=frozenset(),
            ),
            FindingProducer(
                producer_id="curation_lens",
                namespace="health_checks",
                source_module="graph/health_checks/test.py",
                rules=(),
                sections=(),
                metrics_schema=None,
                remediators=frozenset(),
            ),
        ],
        active_kinds=frozenset(),
    )
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _seed_entity(a, "dataset:a")
    _seed_entity(b, "dataset:a")
    early = _report(
        ingestion_ref="ing:early",
        generated_at="2026-07-27T10:00:00+00:00",
        findings=[ReportedFinding(producer_id="curation_lens", finding=_finding())],
    )
    late = _report(
        ingestion_ref="ing:late",
        generated_at="2026-07-27T14:00:00+00:00",
        findings=[ReportedFinding(producer_id="dataset_anomalies", finding=_finding())],
    )

    ingest_report(a, early, registry)
    early_genesis = load_cases(a)[0].transitions[0]
    ingest_report(a, late, registry)
    ingest_report(b, late, registry)
    prior = load_cases(b)[0]
    late_genesis = prior.transitions[0]
    assert late_genesis.actor == "ingest"
    ingest_report(b, early, registry)

    first = load_cases(a)[0]
    second = load_cases(b)[0]
    assert _canonical_state(first) == _canonical_state(second)
    assert first.transitions[0] == early_genesis
    assert second.transitions[0] == late_genesis
    assert first.transitions[0].at.isoformat() == "2026-07-27T10:00:00+00:00"
    assert second.transitions[0].at.isoformat() == "2026-07-27T14:00:00+00:00"
    assert first.transitions[0].actor == "ingest"
    assert second.transitions[0].actor == "ingest"
    assert first.transitions[0].reason == "detected by curation_lens"
    assert second.transitions[0].reason == "detected by dataset_anomalies"
    assert [(occurrence.observed_at, occurrence.idempotency_key) for occurrence in first.occurrences] == sorted(
        (occurrence.observed_at, occurrence.idempotency_key) for occurrence in first.occurrences
    )


@pytest.mark.parametrize(
    "subject",
    [
        pytest.param(
            {"type": "path", "path": "doc/cafe\u0301.md"},
            id="path",
        ),
        pytest.param(
            {
                "type": "identifier",
                "namespace": "reference",
                "value": "cafe\u0301",
            },
            id="identifier",
        ),
    ],
)
def test_unicode_identity_spellings_are_arrival_order_independent(tmp_path, subject):
    from science_model.audit import IdentifierSubject, PathSubject

    unicode_rule = FindingRule(
        id="refs.unicode-identity",
        severities={"warn"},
        subject_types={subject["type"]},
        identifier_namespaces=({"reference"} if subject["type"] == "identifier" else set()),
        qualifier_schema=Q,
        identity_qualifiers=("field",),
        title="t",
        section="datasets",
        display_order=102,
    )
    registry = build_registry(
        [
            FindingProducer(
                producer_id="dataset_anomalies",
                namespace="health_checks",
                source_module="graph/health_checks/test.py",
                rules=(unicode_rule,),
                sections=(SECTION,),
                metrics_schema=None,
                remediators=frozenset(),
            )
        ],
        active_kinds=frozenset(),
    )
    first_subject = (
        PathSubject(path=subject["path"])
        if subject["type"] == "path"
        else IdentifierSubject(
            namespace=subject["namespace"],
            value=subject["value"],
        )
    )
    second_subject = (
        PathSubject(path="doc/café.md")
        if subject["type"] == "path"
        else IdentifierSubject(namespace="reference", value="café")
    )
    projects = [tmp_path / "first", tmp_path / "second"]
    for project in projects:
        project.mkdir()
        if subject["type"] == "path":
            path = project / "doc" / "café.md"
            path.parent.mkdir()
            path.write_text("subject", encoding="utf-8")

    early = _report(
        ingestion_ref="ing:early",
        generated_at="2026-07-27T10:00:00+00:00",
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=AuditFinding(
                    rule_id=unicode_rule.id,
                    subject=first_subject,
                    severity="warn",
                    qualifiers={"field": "anne\u0301e"},
                    message="early",
                ),
            )
        ],
    )
    late = _report(
        ingestion_ref="ing:late",
        generated_at="2026-07-27T14:00:00+00:00",
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=AuditFinding(
                    rule_id=unicode_rule.id,
                    subject=second_subject,
                    severity="warn",
                    qualifiers={"field": "année"},
                    message="late",
                ),
            )
        ],
    )

    ingest_report(projects[0], early, registry)
    early_genesis = load_cases(projects[0])[0].transitions[0]
    ingest_report(projects[0], late, registry)
    ingest_report(projects[1], late, registry)
    late_genesis = load_cases(projects[1])[0].transitions[0]
    ingest_report(projects[1], early, registry)

    left = load_cases(projects[0])[0]
    right = load_cases(projects[1])[0]
    assert _canonical_state(left) == _canonical_state(right)
    assert left.transitions[0] == early_genesis
    assert right.transitions[0] == late_genesis
    assert left.identity_qualifiers["field"] == "année"
    assert {occurrence.qualifiers["field"] for occurrence in left.occurrences} == {"année"}


def test_direct_ingestion_validates_the_canonical_identity_value_before_writing(
    tmp_path,
):
    class DecomposedOnlyQualifier(BaseModel):
        model_config = ConfigDict(extra="forbid")
        field: str = Field(pattern="^cafe\u0301$")

    rule = FindingRule(
        id="dataset.nfc-constrained",
        severities={"warn"},
        subject_types={"entity"},
        qualifier_schema=DecomposedOnlyQualifier,
        identity_qualifiers=("field",),
        title="t",
        section="datasets",
        display_order=103,
    )
    registry = build_registry(
        [
            FindingProducer(
                producer_id="dataset_anomalies",
                namespace="health_checks",
                source_module="graph/health_checks/test.py",
                rules=(rule,),
                sections=(SECTION,),
                metrics_schema=None,
                remediators=frozenset(),
            )
        ],
        active_kinds=frozenset(),
    )
    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=AuditFinding(
                    rule_id=rule.id,
                    subject=EntitySubject(ref="dataset:a"),
                    severity="warn",
                    qualifiers={"field": "cafe\u0301"},
                    message="raw spelling passes; canonical spelling must not",
                ),
            )
        ]
    )

    with pytest.raises(IngestError, match="qualifiers invalid"):
        ingest_report(tmp_path, report, registry)
    assert not (tmp_path / CASES_DIRNAME).exists()


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
        findings=[ReportedFinding(producer_id="who", finding=_finding())],
        meta={
            "producers_run": ["who"],
            "total_duration_seconds": 0.1,
            "timings": [],
        },
    )
    with pytest.raises(IngestError, match="unregistered producer"):
        ingest_report(tmp_path, report, REGISTRY)


def test_unknown_producer_provenance_is_refused_everywhere_before_store_creation(
    tmp_path,
):
    from science_model.audit import ProducerMetrics, UnwiredProducer

    reports = [
        _report(
            findings=[],
            totals={
                "findings_total": 0,
                "findings_by_severity": {},
                "accepted_total": 0,
                "unwired_total": 0,
            },
            meta={
                "producers_run": ["unknown"],
                "total_duration_seconds": 0.1,
                "timings": [],
            },
        ),
        _report(
            findings=[],
            unwired=[
                UnwiredProducer(
                    producer_id="unknown",
                    code="not-wired",
                    reason="missing",
                )
            ],
            totals={
                "findings_total": 0,
                "findings_by_severity": {},
                "accepted_total": 0,
                "unwired_total": 1,
            },
            meta={
                "producers_run": [],
                "total_duration_seconds": 0.1,
                "timings": [],
            },
        ),
        _report(
            findings=[],
            metrics={"unknown": ProducerMetrics(scanned=1)},
            totals={
                "findings_total": 0,
                "findings_by_severity": {},
                "accepted_total": 0,
                "unwired_total": 0,
            },
            meta={
                "producers_run": ["unknown"],
                "total_duration_seconds": 0.1,
                "timings": [],
            },
        ),
    ]

    for report in reports:
        with pytest.raises(IngestError, match="unregistered producer"):
            ingest_report(tmp_path, report, REGISTRY)
        assert not (tmp_path / CASES_DIRNAME).exists()


def test_unknown_accepted_producer_is_refused_before_store_creation(tmp_path):
    from science_model.audit import AcceptedFinding

    report = _report(
        findings=[],
        accepted=[
            AcceptedFinding(
                producer_id="unknown",
                finding=_finding(),
                acceptance_key="b" * 32,
                reason="known",
            )
        ],
        meta={
            "producers_run": ["unknown"],
            "total_duration_seconds": 0.1,
            "timings": [],
        },
    )
    with pytest.raises(IngestError, match="unregistered producer"):
        ingest_report(tmp_path, report, REGISTRY)
    assert not (tmp_path / CASES_DIRNAME).exists()


def test_registered_producer_may_run_and_emit_no_output(tmp_path):
    report = _report(
        findings=[],
        totals={
            "findings_total": 0,
            "findings_by_severity": {},
            "accepted_total": 0,
            "unwired_total": 0,
        },
    )

    outcome = ingest_report(tmp_path, report, REGISTRY)

    assert outcome.records_written == 0
    assert outcome.occurrences_appended == 0
    assert outcome.occurrences_skipped == 0


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
        _ingest_report(
            tmp_path,
            report,
            REGISTRY,
            provenance=IngestionProvenance(
                ingestion_ref="ing:1",
                generated_at="2026-07-27T12:00:00+00:00",
                producer_ids=frozenset({"dataset_anomalies"}),
            ),
            context=IngestionContext(canonical_entity_ids=frozenset({"dataset:a", "dataset:b"})),
        )
    assert not (tmp_path / "doc").exists()


def test_ingest_revalidates_a_model_copy_with_a_forged_schema_version(tmp_path):
    forged = _report().model_copy(update={"schema_version": 99})

    _assert_forged_report_is_refused_without_mutation(tmp_path, forged)


def test_ingest_revalidates_a_model_copy_with_forged_totals(tmp_path):
    report = _report()
    forged_totals = report.totals.model_copy(update={"findings_total": 0})
    forged = report.model_copy(update={"totals": forged_totals})

    _assert_forged_report_is_refused_without_mutation(tmp_path, forged)


def test_direct_ingestion_refuses_combined_count_before_store_creation(tmp_path):
    from science_tool.findings.ingest import MAX_INGESTED_REPORT_FINDINGS

    finding = ReportedFinding(producer_id="dataset_anomalies", finding=_finding())
    accepted = AcceptedFinding(
        producer_id="dataset_anomalies",
        finding=_finding(),
        acceptance_key="a" * 32,
        reason="known",
    )
    half = MAX_INGESTED_REPORT_FINDINGS // 2
    report = _report(
        findings=[finding] * (half + 1),
        accepted=[accepted] * (MAX_INGESTED_REPORT_FINDINGS - half),
    )
    with pytest.raises(IngestError, match="ceiling"):
        ingest_report(tmp_path, report, REGISTRY)
    assert not (tmp_path / CASES_DIRNAME).exists()


def test_direct_ingestion_rechecks_count_on_the_detached_snapshot(tmp_path):
    from science_tool.findings.ingest import MAX_INGESTED_REPORT_FINDINGS

    class LengthLiar(tuple):
        def __len__(self):
            return 0

    report = _report()
    actual_count = MAX_INGESTED_REPORT_FINDINGS + 1
    forged = report.model_copy(
        update={
            "findings": LengthLiar(report.findings * actual_count),
            "totals": report.totals.model_copy(
                update={
                    "findings_total": actual_count,
                    "findings_by_severity": {"warn": actual_count},
                }
            ),
        }
    )

    with pytest.raises(IngestError, match="ceiling"):
        ingest_report(tmp_path, forged, REGISTRY)
    assert not (tmp_path / CASES_DIRNAME).exists()


def test_load_report_refuses_combined_count_before_any_store_access(tmp_path):
    from science_tool.findings.ingest import MAX_INGESTED_REPORT_FINDINGS

    finding = ReportedFinding(producer_id="dataset_anomalies", finding=_finding())
    accepted = AcceptedFinding(
        producer_id="dataset_anomalies",
        finding=_finding(),
        acceptance_key="a" * 32,
        reason="known",
    )
    half = MAX_INGESTED_REPORT_FINDINGS // 2
    report = _report(
        findings=[finding] * (half + 1),
        accepted=[accepted] * (MAX_INGESTED_REPORT_FINDINGS - half),
    )
    payload = report.model_dump(mode="json")
    path = tmp_path / "report.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(IngestError, match="ceiling"):
        load_report(tmp_path, path)
    assert not (tmp_path / CASES_DIRNAME).exists()


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


def test_direct_ingestion_refuses_an_oversized_snapshot_before_store_creation(
    tmp_path,
):
    from science_tool.findings.ingest import MAX_REPORT_BYTES

    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(message="é" * (MAX_REPORT_BYTES // 2 + 1)),
            )
        ]
    )

    with pytest.raises(IngestError, match="exceeds"):
        ingest_report(tmp_path, report, REGISTRY)

    assert not (tmp_path / CASES_DIRNAME).exists()
    assert not (tmp_path / "doc").exists()


def test_ingest_snapshots_and_revalidates_mutable_report_lists(tmp_path):
    report = _report()
    findings_alias = list(report.findings)
    forged = report.model_copy(update={"findings": findings_alias})
    findings_alias.append(
        ReportedFinding(
            producer_id="dataset_anomalies",
            finding=_finding(subject=EntitySubject(ref="dataset:b")),
        )
    )

    _assert_forged_report_is_refused_without_mutation(tmp_path, forged)


def test_ingest_wraps_a_cyclic_mutation_during_report_snapshot(tmp_path):
    report = _report()
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    forged_meta = report.meta.model_copy(update={"timings": [cyclic]})
    forged = report.model_copy(update={"meta": forged_meta})

    _assert_forged_report_is_refused_without_mutation(tmp_path, forged)


def test_partial_failure_is_repaired_by_rerunning_the_same_report(tmp_path):
    # Simulate a crash after the first of two records is written, by writing the
    # first record alone and then re-ingesting the whole report.
    first_only = _report(findings=[ReportedFinding(producer_id="dataset_anomalies", finding=_finding())])
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


def test_oversized_second_record_is_preflighted_before_any_case_write(tmp_path):
    subjects = [EntitySubject(ref="dataset:a"), EntitySubject(ref="dataset:b")]
    first_subject, second_subject = sorted(
        subjects,
        key=lambda subject: finding_fingerprint(
            rule_id=RULE.id,
            subject=subject,
            identity_qualifiers={"field": "year"},
        ),
    )
    oversized = "é" * (MAX_CASE_BYTES // 2 + 1)
    report = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(subject=first_subject),
            ),
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(subject=second_subject, message=oversized),
            ),
        ]
    )

    with pytest.raises(IngestError, match="exceeds"):
        ingest_report(tmp_path, report, REGISTRY)

    assert load_cases(tmp_path) == []
    cases = tmp_path / CASES_DIRNAME
    assert sorted(entry.name for entry in cases.iterdir()) == [".ingest.lock"]

    repaired = _report(
        findings=[
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(subject=first_subject),
            ),
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(subject=second_subject),
            ),
        ]
    )
    outcome = ingest_report(tmp_path, repaired, REGISTRY)
    assert outcome.records_written == 2
    assert len(load_cases(tmp_path)) == 2
    assert not any(entry.name.endswith(".tmp") for entry in cases.iterdir())


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

    with pytest.raises(IngestError, match="could not parse.*excessive nesting"):
        load_report(tmp_path, path)


EXPECTED_MAX_REPORT_NESTING = 100


def _nested_list(depth: int) -> object:
    value: object = 0
    for _ in range(depth):
        value = [value]
    return value


def _report_with_metric_nesting(depth: int) -> dict:
    report = _report(
        metrics={
            "dataset_anomalies": {
                "nested": _nested_list(depth),
            }
        }
    )
    return report.model_dump(mode="json")


def test_load_report_accepts_the_maximum_json_nesting(tmp_path):
    path = tmp_path / "report.json"
    # root object + metrics object + producer object consume three levels.
    path.write_text(
        json.dumps(_report_with_metric_nesting(EXPECTED_MAX_REPORT_NESTING - 3)),
        encoding="utf-8",
    )

    assert load_report(tmp_path, path).schema_version == 2


def test_load_report_refuses_one_level_beyond_maximum_json_nesting(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(_report_with_metric_nesting(EXPECTED_MAX_REPORT_NESTING - 2)),
        encoding="utf-8",
    )

    with pytest.raises(IngestError, match="could not parse.*excessive nesting"):
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


@pytest.mark.parametrize("renamed", ["notes.md", ".hidden.md"])
def test_ingestion_refuses_a_renamed_case_before_writing_a_replacement(
    tmp_path,
    renamed,
):
    from science_tool.findings.storage import case_path

    ingest_report(tmp_path, _report(), REGISTRY)
    record = load_cases(tmp_path)[0]
    canonical = case_path(tmp_path, record)
    renamed_path = canonical.with_name(renamed)
    original = canonical.read_bytes()
    canonical.rename(renamed_path)

    with pytest.raises(IngestError):
        ingest_report(tmp_path, _report(ingestion_ref="ing:2"), REGISTRY)

    assert renamed_path.read_bytes() == original
    assert not canonical.exists()


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
                finding=_finding(qualifiers={"field": "year", "note": "first look"}),
            ),
            ReportedFinding(
                producer_id="dataset_anomalies",
                finding=_finding(qualifiers={"field": "year", "note": "second look"}),
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
                source_module="graph/health_checks/test.py",
                rules=(RULE, path_rule),
                sections=(SECTION,),
                metrics_schema=None,
                remediators=frozenset(),
            )
        ],
        active_kinds=frozenset(),
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
                finding=_finding(evidence=[LocationEvidence(path="doc/x.md", line=1)]),
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
