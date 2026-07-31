from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from click.testing import CliRunner
from science_model.audit import EntitySubject, LocationEvidence, finding_fingerprint

from science_tool.cli import main
from science_tool.graph.health import build_health_report
from science_tool.graph.health_checks.dataset_anomalies import (
    CHECK as DATASET_ANOMALIES_CHECK,
    DATASET_RULE_CODES,
    RULES as DATASET_RULES,
)
from science_tool.graph.health_checks.base import HealthContext
from science_tool.graph.sources import ProjectSources

_ACTOR = {
    "ingestion_ref": "health:test",
    "generated_at": "2026-07-28T12:00:00+00:00",
}


def _report(root: Path, **kwargs: object):
    return build_health_report(root, **_ACTOR, **kwargs)


def test_health_report_is_audit_report_v2(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    report = _report(tmp_path, checks={"tooling_scaffold"})
    assert report.schema_version == 2
    assert report.ingestion_ref == "health:test"
    assert report.totals.findings_total == len(report.findings)
    assert report.meta.producers_run == ("tooling_scaffold",)
    assert {item.finding.rule_id for item in report.findings} == {"tooling.scaffold"}


def test_health_requires_actor_claims(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        build_health_report(tmp_path)  # type: ignore[call-arg]


def test_selected_source_check_loads_sources_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import science_tool.graph.health as health

    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    real = health.load_project_sources
    calls = 0

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real(root, **kwargs)

    monkeypatch.setattr(health, "load_project_sources", counted)
    report = _report(tmp_path, checks={"unresolved_refs"})
    assert calls == 1
    assert report.totals.unwired_total == 1
    assert {item.producer_id for item in report.unwired} == {"unresolved_refs"}
    assert report.meta.producers_run == ("schema_invalid",)


def test_fast_health_never_loads_project_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import science_tool.graph.health as health

    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("fast health loaded project sources")

    monkeypatch.setattr(health, "load_project_sources", fail)
    report = _report(tmp_path, fast=True)
    assert "identity_policy" not in report.meta.producers_run


def test_health_parses_each_task_once_per_commons_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections import Counter
    from datetime import date

    from science_model.tasks import Task

    from science_tool.graph.storage_adapters import task as task_adapter
    from science_tool.tasks import render_task_file

    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    active = tmp_path / "tasks" / "active"
    active.mkdir(parents=True)
    for index in range(2):
        task = Task(
            id=f"t{index:03d}",
            title=f"Task {index}",
            priority="P2",
            status="active",
            created=date(2026, 1, 1),
        )
        (active / f"{task.id}-task.md").write_text(render_task_file(task), encoding="utf-8")

    real = task_adapter._parse_task_path
    parsed: list[str] = []

    def counted(path: Path):
        parsed.append(path.name)
        return real(path)

    monkeypatch.setattr(task_adapter, "_parse_task_path", counted)

    _report(tmp_path)

    assert Counter(parsed) == {"t000-task.md": 2, "t001-task.md": 2}


def test_agent_context_rows_are_declared_findings(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("@AGENTS.md\n@core/overview.md\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Guide\n", encoding="utf-8")
    report = _report(tmp_path, checks={"agent_context"})
    assert report.totals.findings_total >= 1
    assert all(item.finding.rule_id.startswith("agent-context.") for item in report.findings)


def test_dataset_declared_rule_ids_equal_complete_code_ledger() -> None:
    assert len(DATASET_RULE_CODES) == 12
    assert set(DATASET_RULES) == set(DATASET_RULE_CODES)
    assert {rule.id for rule in DATASET_RULES.values()} == {
        f"dataset.{code.removeprefix('dataset_').replace('_', '-')}" for code in DATASET_RULE_CODES
    }


def test_dataset_rule_contracts_and_fingerprints_match_the_frozen_table() -> None:
    expected = {
        "dataset_access_invalid": ({"error"}, (), ()),
        "dataset_consumed_but_unverified": ({"error"}, (), ()),
        "dataset_stale_review": ({"warn"}, (), ()),
        "dataset_missing_source_url": ({"warn"}, (), ()),
        "dataset_cached_field_drift": ({"warn"}, ("field",), ("field",)),
        "dataset_invariant_violation": (
            {"warn"},
            ("invariant", "counterpart"),
            ("invariant", "counterpart"),
        ),
        "dataset_derived_missing_workflow_run": ({"error"}, (), ()),
        "dataset_derived_asymmetric_edge": (
            {"error"},
            ("counterpart",),
            ("counterpart",),
        ),
        "dataset_derived_input_chain_broken": (
            {"error"},
            ("counterpart",),
            ("counterpart",),
        ),
        "dataset_origin_block_mismatch": ({"error"}, ("field",), ("field",)),
        "dataset_verified_but_unstageable": ({"warn"}, (), ()),
        "dataset_research_package_asymmetric": (
            {"error"},
            ("counterpart",),
            ("counterpart",),
        ),
    }
    assert set(DATASET_RULES) == set(expected)
    for code, (severities, fields, identity) in expected.items():
        rule = DATASET_RULES[code]
        assert rule.severities == frozenset(severities)
        assert rule.subject_types == frozenset({"entity"})
        assert tuple(rule.qualifier_schema.model_fields) == fields
        assert rule.identity_qualifiers == identity

        qualifiers = {field: f"{field}:one" for field in fields}
        first = rule.build(
            subject=EntitySubject(ref="dataset:one"),
            severity=next(iter(severities)),
            qualifiers=qualifiers,
            message="first wording",
        )
        first_id = finding_fingerprint(
            rule_id=first.rule_id,
            subject=first.subject,
            identity_qualifiers=rule.identity_subset(first.qualifiers),
        )
        if fields:
            changed = dict(qualifiers)
            changed[fields[0]] = f"{fields[0]}:two"
            second = rule.build(
                subject=first.subject,
                severity=first.severity,
                qualifiers=changed,
                message=first.message,
            )
            second_id = finding_fingerprint(
                rule_id=second.rule_id,
                subject=second.subject,
                identity_qualifiers=rule.identity_subset(second.qualifiers),
            )
            assert second_id != first_id
        else:
            reworded = first.model_copy(update={"message": "different wording"})
            reworded_id = finding_fingerprint(
                rule_id=reworded.rule_id,
                subject=reworded.subject,
                identity_qualifiers=rule.identity_subset(reworded.qualifiers),
            )
            assert reworded_id == first_id


def test_dataset_anomaly_evidence_path_is_relative_to_resolved_project_root(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "entities" / "datasets" / "d.md"
    dataset.parent.mkdir(parents=True)
    dataset.write_text(
        """\
---
id: dataset:d
kind: dataset
origin: external
derivation: {}
access: {}
---
""",
        encoding="utf-8",
    )
    context = HealthContext(
        project_root=tmp_path.resolve(),
        sources=cast(
            ProjectSources,
            SimpleNamespace(entities=[SimpleNamespace(canonical_id="dataset:d")]),
        ),
    )

    result = DATASET_ANOMALIES_CHECK.run(context)

    finding = result.instrument.rows[0]
    assert finding.evidence == (LocationEvidence(path="entities/datasets/d.md"),)


def test_health_cli_does_not_rebuild_the_registry_after_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import science_tool.findings.catalog as catalog

    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")

    def changed_configuration(_root: Path):
        raise AssertionError("project configuration changed after health execution")

    monkeypatch.setattr(catalog, "build_project_registry", changed_configuration)
    result = CliRunner().invoke(
        main,
        [
            "health",
            "--project-root",
            str(tmp_path),
            "--check",
            "unresolved_refs",
        ],
    )
    assert result.exit_code == 0, result.output


def test_health_cli_json_is_exact_report_v2(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    result = CliRunner().invoke(
        main,
        [
            "health",
            "--project-root",
            str(tmp_path),
            "--format",
            "json",
            "--check",
            "tooling_scaffold",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == 2
    assert payload["ingestion_ref"].startswith("health:")
    assert set(payload) == {
        "schema_version",
        "fingerprint_version",
        "ingestion_ref",
        "generated_at",
        "findings",
        "accepted",
        "metrics",
        "caveats",
        "unwired",
        "totals",
        "meta",
    }


def test_unknown_health_check_fails_early(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown health check"):
        _report(tmp_path, checks={"ghost"})
