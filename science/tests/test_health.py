from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.health import build_health_report
from science_tool.graph.health_checks.dataset_anomalies import (
    DATASET_RULE_CODES,
    RULES as DATASET_RULES,
)

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
