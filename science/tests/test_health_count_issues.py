import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from science_model.audit import (
    LocationEvidence,
    finding_fingerprint,
)

from science_tool.data_audit import (
    AuditNote,
    DATA_AUDIT_PRODUCER,
    DataAuditSnapshot,
    Quadrant,
    Violation,
    data_audit_result,
)
from science_tool.data_policy import FileClass
from science_tool.findings.catalog import build_project_registry
from science_tool.findings.producers import (
    FindingProducerResult,
    validate_producer_result,
)
from science_tool.findings.reporting import build_audit_report
from science_tool.graph.health import build_health_report
from science_tool.graph.health_checks import (
    HEALTH_CHECKS,
    agent_context,
    cross_paper_evidence,
    dataset_anomalies,
    entity_identity,
    identity_policy,
    invalid_entity_aspects,
    layered_claim_migration,
    legacy_task_type,
    lingering_tags,
    managed_artifacts,
    prose_epistemics,
    tooling_scaffold,
    unregistered_ref_kinds,
    unresolved_refs,
    validate as validate_health,
)
from science_tool.graph.health_checks.base import HealthContext
from science_tool.graph.health_checks.schema_invalid import (
    SCHEMA_INVALID_PRODUCER,
    produce_schema_invalid,
)
from science_tool.graph.sources import ProjectSources, SkippedEntity
from science_tool.instruments import InstrumentResult


_LEDGER_PRODUCERS = {
    "unresolved_refs",
    "unregistered_ref_kinds",
    "lingering_tags",
    "agent_context",
    "identity_policy",
    "entity_identity",
    "layered_claim_migration",
    "cross_paper_evidence",
    "managed_artifacts",
    "tooling_scaffold",
    "validate",
    "prose_epistemics",
    "dataset_anomalies",
    "legacy_task_type",
    "invalid_entity_aspects",
}


def test_count_ledger_is_exhaustive_and_every_producer_uses_one_report_channel(
    tmp_path: Path,
) -> None:
    assert {check.producer.producer_id for check in HEALTH_CHECKS} == _LEDGER_PRODUCERS
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    report = build_health_report(
        tmp_path,
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
    )

    accounted = set(report.meta.producers_run) | {item.producer_id for item in report.unwired}
    assert accounted == _LEDGER_PRODUCERS | {"schema_invalid"}
    assert report.totals.findings_total == len(report.findings)
    assert sum(report.totals.findings_by_severity.values()) == len(report.findings)


def _one_issue_result(
    producer_id: str,
    context: HealthContext,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[FindingProducerResult, int]:
    one = InstrumentResult.from_rows
    if producer_id == "unresolved_refs":
        monkeypatch.setattr(
            unresolved_refs,
            "collect_unresolved_refs",
            lambda *_args, **_kwargs: one(
                [
                    {
                        "target": "question:missing",
                        "mention_count": 1,
                        "sources": ["doc/note.md"],
                        "looks_like": "unknown",
                    }
                ]
            ),
        )
    elif producer_id == "unregistered_ref_kinds":
        monkeypatch.setattr(
            unregistered_ref_kinds,
            "collect_unregistered_ref_kinds",
            lambda *_args, **_kwargs: one(
                [
                    {
                        "kind": "unknown",
                        "field": "related",
                        "mention_count": 1,
                        "refs": ["unknown:x"],
                        "sources": ["entities/questions/q.md"],
                    }
                ]
            ),
        )
    elif producer_id == "lingering_tags":
        monkeypatch.setattr(
            lingering_tags,
            "collect_lingering_tags",
            lambda *_args, **_kwargs: one([{"file": "doc/note.md", "values": ["legacy"]}]),
        )
    elif producer_id == "agent_context":
        monkeypatch.setattr(
            agent_context,
            "collect_agent_context_findings",
            lambda *_args, **_kwargs: one(
                [
                    {
                        "code": "claude_md_not_minimal",
                        "source_file": "CLAUDE.md",
                        "detail": "CLAUDE.md is not minimal.",
                        "fix": "Replace it with @AGENTS.md.",
                    }
                ]
            ),
        )
    elif producer_id == "identity_policy":
        monkeypatch.setattr(
            identity_policy,
            "collect_identity_policy_findings",
            lambda *_args, **_kwargs: one(
                [
                    {
                        "check": "primary_external_id_collision",
                        "entity_id": "question:q",
                        "source_file": "entities/questions/q.md",
                        "message": "Identity policy violation.",
                    }
                ]
            ),
        )
    elif producer_id == "entity_identity":
        monkeypatch.setattr(
            entity_identity,
            "_collect_entity_identity",
            lambda *_args, **_kwargs: [
                {
                    "code": "invalid_id",
                    "severity": "warning",
                    "message": "Entity identity warning.",
                    "path": "entities/questions/q.md",
                    "canonical_id": "question:q",
                }
            ],
        )
    elif producer_id == "layered_claim_migration":
        monkeypatch.setattr(
            layered_claim_migration,
            "build_layered_claim_migration_report",
            lambda *_args, **_kwargs: {
                "rows": [
                    {
                        "proposition": "proposition:p",
                        "source_path": "entities/propositions/p.md",
                        "authored_claim_layer": None,
                        "authored_identification_strength": None,
                        "inferred_identification_strength": None,
                        "warnings": ["Missing layered claim metadata."],
                        "todos": [],
                    }
                ],
                "summary": {
                    "authored_claim_layer_count": 1,
                    "proposition_count": 1,
                },
            },
        )
    elif producer_id == "cross_paper_evidence":
        monkeypatch.setattr(
            cross_paper_evidence,
            "_collect_cross_paper_evidence",
            lambda *_args, **_kwargs: {
                "status": "fail",
                "empty_state": "active",
                "summary": {
                    "propositions": 0,
                    "propositions_with_units": 0,
                    "units": 0,
                    "faults": 1,
                    "faults_by_reason": {"sidecar-parse-error": 1},
                    "contested": 0,
                },
                "findings": [
                    {
                        "code": "cross_paper_evidence.sidecar-parse-error",
                        "severity": "error",
                        "sidecar": "knowledge/annotations/bad.json",
                        "annotation": "annotation:bad",
                        "reason": "sidecar-parse-error",
                        "detail": "Sidecar cannot be parsed.",
                    }
                ],
                "propositions": [],
            },
        )
    elif producer_id == "managed_artifacts":
        monkeypatch.setattr(
            managed_artifacts,
            "_collect_managed_artifacts",
            lambda *_args, **_kwargs: [
                {
                    "name": "commands",
                    "install_target": ".claude/commands",
                    "version": "v1",
                    "status": "stale",
                    "detail": "Managed commands are stale.",
                    "counts_as_issue": True,
                },
                {
                    "name": "skills",
                    "install_target": ".claude/skills",
                    "version": "v1",
                    "status": "current",
                    "detail": "Managed skills are current.",
                    "counts_as_issue": False,
                },
            ],
        )
    elif producer_id == "prose_epistemics":
        monkeypatch.setattr(
            prose_epistemics,
            "_collect_prose_epistemics",
            lambda *_args, **_kwargs: {
                "applicable": True,
                "summary": {},
                "coverage": {},
                "sources": [],
                "findings": [
                    {
                        "code": "missing_decomposition",
                        "severity": "warning",
                        "counts_as_issue": True,
                        "source_ref": "report:r",
                        "path": "annotations/prose-health.json",
                        "message": "Decomposition is missing.",
                    },
                    {
                        "code": "missing_grounding",
                        "severity": "warning",
                        "counts_as_issue": False,
                        "source_ref": "report:r",
                        "path": "annotations/prose-health.json",
                        "message": "Grounding is informational.",
                    },
                ],
            },
        )
    elif producer_id == "dataset_anomalies":
        monkeypatch.setattr(
            dataset_anomalies,
            "check_dataset_anomalies",
            lambda *_args, **_kwargs: one(
                [
                    {
                        "code": "dataset_access_invalid",
                        "severity": "error",
                        "entity_id": "dataset:d",
                        "file_path": "entities/datasets/d.md",
                        "message": "Dataset access is invalid.",
                    }
                ]
            ),
        )
    elif producer_id == "legacy_task_type":
        monkeypatch.setattr(
            legacy_task_type,
            "collect_legacy_task_type",
            lambda *_args, **_kwargs: one(
                [
                    {
                        "task_id": "t001",
                        "legacy_type": "dev",
                        "source_file": "tasks/active/t001.md",
                    }
                ]
            ),
        )
    elif producer_id == "invalid_entity_aspects":
        monkeypatch.setattr(
            invalid_entity_aspects,
            "collect_invalid_entity_aspects",
            lambda *_args, **_kwargs: one(
                [
                    {
                        "entity_id": "question:q",
                        "source_file": "entities/questions/q.md",
                        "message": "Unknown aspect.",
                    }
                ]
            ),
        )
    elif producer_id == "tooling_scaffold":
        return tooling_scaffold.CHECK.run(context), 1
    elif producer_id == "validate":
        doc = context.project_root / "doc" / "note.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "Smith 2020 reported this result.\nJones 2021 repeated it.\n",
            encoding="utf-8",
        )
        result = validate_health.CHECK.run(context)
        assert sum(finding.rule_id == "prose-lints.hit" for finding in result.instrument.rows) == 2
        return result, len(result.instrument.rows)
    else:
        raise AssertionError(f"missing count-ledger fixture for {producer_id}")

    check = next(check for check in HEALTH_CHECKS if check.name == producer_id)
    return check.run(context), 1


@pytest.mark.parametrize(
    "producer_id",
    (*sorted(_LEDGER_PRODUCERS), "schema_invalid"),
)
def test_each_count_ledger_row_executes_its_real_producer_and_preserves_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    producer_id: str,
) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )
    registry = build_project_registry(tmp_path)
    if producer_id == "schema_invalid":
        result = produce_schema_invalid(
            [
                SkippedEntity(
                    path="entities/questions/bad.md",
                    kind="question",
                    reason="entity_schema_validation_failed",
                    details="missing required field",
                )
            ]
        )
        producer = SCHEMA_INVALID_PRODUCER
        expected_count = 1
    else:
        source_entities = [SimpleNamespace(canonical_id="dataset:d")] if producer_id == "dataset_anomalies" else []
        context = HealthContext(
            project_root=tmp_path,
            sources=cast(
                ProjectSources,
                SimpleNamespace(entities=source_entities),
            ),
        )
        result, expected_count = _one_issue_result(
            producer_id,
            context,
            monkeypatch,
        )
        producer = next(check.producer for check in HEALTH_CHECKS if check.name == producer_id)

    validated = validate_producer_result(
        registry,
        producer.producer_id,
        result,
    )
    assert len(validated.instrument.rows) == expected_count

    report = build_audit_report(
        producer_results={producer.producer_id: validated},
        registry=registry,
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
        total_duration_seconds=0,
    )
    assert report.totals.findings_total == len(report.findings)
    assert sum(report.totals.findings_by_severity.values()) == len(report.findings)


@pytest.mark.parametrize(
    ("ledger_row", "report_rows", "summary", "entities", "expected_rule"),
    (
        (
            "migration",
            [
                {
                    "proposition": "proposition:p",
                    "source_path": "entities/propositions/p.md",
                    "authored_claim_layer": None,
                    "authored_identification_strength": None,
                    "inferred_identification_strength": None,
                    "warnings": ["Missing layered claim metadata."],
                    "todos": [],
                }
            ],
            {
                "authored_claim_layer_count": 1,
                "proposition_count": 1,
            },
            [],
            "layered-claim.migration",
        ),
        (
            "rival-model-gap",
            [],
            {
                "authored_claim_layer_count": 1,
                "proposition_count": 1,
            },
            [
                SimpleNamespace(
                    kind="proposition",
                    canonical_id="proposition:p",
                    file_path="entities/propositions/p.md",
                    rival_model_packet=SimpleNamespace(
                        packet_id="rival:p",
                        discriminating_predictions=[],
                    ),
                )
            ],
            "layered-claim.rival-model-gap",
        ),
        (
            "claim-layer-coverage",
            [],
            {
                "authored_claim_layer_count": 0,
                "proposition_count": 1,
            },
            [],
            "layered-claim.coverage-incomplete",
        ),
        (
            "identification-strength-coverage",
            [
                {
                    "proposition": "proposition:p",
                    "source_path": "entities/propositions/p.md",
                    "authored_claim_layer": "causal_effect",
                    "authored_identification_strength": None,
                    "inferred_identification_strength": None,
                    "warnings": [],
                    "todos": [],
                }
            ],
            {
                "authored_claim_layer_count": 1,
                "proposition_count": 1,
            },
            [],
            "layered-claim.coverage-incomplete",
        ),
    ),
)
def test_each_layered_claim_ledger_subrow_contributes_one_finding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ledger_row: str,
    report_rows: list[dict[str, object]],
    summary: dict[str, int],
    entities: list[SimpleNamespace],
    expected_rule: str,
) -> None:
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    monkeypatch.setattr(
        layered_claim_migration,
        "build_layered_claim_migration_report",
        lambda *_args, **_kwargs: {
            "rows": report_rows,
            "summary": summary,
        },
    )
    context = HealthContext(
        project_root=tmp_path,
        sources=cast(
            ProjectSources,
            SimpleNamespace(entities=entities),
        ),
    )

    result = layered_claim_migration.CHECK.run(context)

    assert [finding.rule_id for finding in result.instrument.rows] == [expected_rule], ledger_row
    assert len(result.instrument.rows) == 1


def test_numeric_verification_ledger_row_remains_metrics_only(
    tmp_path: Path,
) -> None:
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    doc = tmp_path / "doc" / "note.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("No numeric claims.\n", encoding="utf-8")

    result = validate_health.CHECK.run(
        HealthContext(project_root=tmp_path),
    )

    assert result.metrics.model_dump(mode="json") == {
        "verified": 0,
        "unverifiable": 0,
        "mismatch": 0,
        "error": 0,
    }
    assert all(finding.rule_id != "prose-lints.numeric-verification.coverage" for finding in result.instrument.rows)


def test_validation_ledger_reduces_only_semantically_identical_prose_hits(
    tmp_path: Path,
) -> None:
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    doc = tmp_path / "doc" / "note.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        "Smith 2020 reported this result.\nSmith 2020 repeated this result.\nJones 2021 reported a distinct result.\n",
        encoding="utf-8",
    )

    report = build_health_report(
        tmp_path,
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
        checks={"validate"},
    )
    prose_hits = [item.finding for item in report.findings if item.finding.rule_id == "prose-lints.hit"]

    assert {finding.qualifiers["match"] for finding in prose_hits} == {"smith 2020", "jones 2021"}
    assert len(prose_hits) == 2
    smith = next(finding for finding in prose_hits if finding.qualifiers["match"] == "smith 2020")
    assert smith.evidence == (
        # Lines remain evidence and never enter the finding identity.
        LocationEvidence(path="doc/note.md", line=1),
        LocationEvidence(path="doc/note.md", line=2),
    )


def test_unwired_ledger_row_stays_out_of_findings_and_totals(
    tmp_path: Path,
) -> None:
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")

    report = build_health_report(
        tmp_path,
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
        checks={"lingering_tags"},
    )

    assert [item.producer_id for item in report.unwired] == ["lingering_tags"]
    assert report.findings == ()
    assert report.totals.findings_total == 0


def test_data_audit_violation_and_warning_note_ledger_rows_each_become_findings(
    tmp_path: Path,
) -> None:
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    result = data_audit_result(
        DataAuditSnapshot(
            violations=(
                Violation(
                    quadrant=Quadrant.STRANDED_RECORD,
                    path="data/processed/run/RESULTS.md",
                    file_class=FileClass.RECORD,
                    proposed_target="results/run/RESULTS.md",
                ),
            ),
            notes=(
                AuditNote(
                    severity="warning",
                    code="tracked-data-root",
                    message="Tracked payload remains.",
                ),
                AuditNote(
                    severity="info",
                    code="policy-note",
                    message="Informational policy note.",
                ),
            ),
        )
    )
    registry = build_project_registry(tmp_path)
    validated = validate_producer_result(
        registry,
        DATA_AUDIT_PRODUCER.producer_id,
        result,
    )

    assert [finding.rule_id for finding in validated.instrument.rows] == [
        "data.violation.stranded-record",
        "data.audit-note",
    ]
    report = build_audit_report(
        producer_results={DATA_AUDIT_PRODUCER.producer_id: validated},
        registry=registry,
        ingestion_ref="data-audit:test",
        generated_at="2026-07-28T12:00:00+00:00",
        total_duration_seconds=0,
    )
    assert report.totals.findings_total == 2


def test_report_total_is_always_finding_row_count(tmp_path: Path) -> None:
    report = build_health_report(
        tmp_path,
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
        checks={"tooling_scaffold", "managed_artifacts"},
    )
    assert report.totals.findings_total == len(report.findings)
    assert sum(report.totals.findings_by_severity.values()) == len(report.findings)


def test_legacy_task_and_invalid_aspects_now_count(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks" / "active"
    tasks.mkdir(parents=True)
    (tasks / "t001.md").write_text(
        "---\nid: t001\ntitle: task\ntype: dev\npriority: P1\n"
        "status: proposed\naspects: []\ncreated: 2026-04-13\n---\nbody\n",
        encoding="utf-8",
    )
    (tmp_path / "science.yaml").write_text(
        "name: test\naspects: [known]\n",
        encoding="utf-8",
    )
    entity = tmp_path / "entities" / "questions" / "q.md"
    entity.parent.mkdir(parents=True)
    entity.write_text(
        "---\nid: question:q\nkind: question\ntitle: Question\naspects: [unknown]\n---\n",
        encoding="utf-8",
    )
    report = build_health_report(
        tmp_path,
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
        checks={"legacy_task_type", "invalid_entity_aspects"},
    )
    producer_ids = [item.producer_id for item in report.findings]
    assert producer_ids.count("legacy_task_type") == 1
    assert producer_ids.count("invalid_entity_aspects") == 1
    assert report.totals.findings_total == 2


def test_accepted_and_unsuppressed_findings_are_disjoint_and_counted(
    tmp_path: Path,
) -> None:
    config = tmp_path / "science.yaml"
    config.write_text("name: test\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    unaccepted_report = build_health_report(
        tmp_path,
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
        checks={"validate"},
    )
    registry = build_project_registry(tmp_path)

    def identity(reported) -> str:
        finding = reported.finding
        rule = registry.rule(finding.rule_id)
        return finding_fingerprint(
            rule_id=finding.rule_id,
            subject=finding.subject,
            identity_qualifiers=rule.identity_subset(finding.qualifiers),
        )

    accepted_finding = next(
        item
        for item in unaccepted_report.findings
        if item.finding.rule_id == "manifest.check" and "missing required field: profile" in item.finding.message
    )
    config.write_text(
        "name: test\n"
        "health:\n"
        "  accepted_validation:\n"
        f"    - finding_id: {identity(accepted_finding)}\n"
        "      fingerprint_version: 1\n"
        "      reason: reviewed\n"
        "      severity_scope: [error]\n",
        encoding="utf-8",
    )
    report = build_health_report(
        tmp_path,
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
        checks={"validate"},
    )

    finding_ids = {identity(item) for item in report.findings}
    accepted_ids = {identity(item) for item in report.accepted}
    assert accepted_ids
    assert finding_ids.isdisjoint(accepted_ids)
    assert report.totals.findings_total == len(finding_ids)
    assert report.totals.accepted_total == len(accepted_ids)
