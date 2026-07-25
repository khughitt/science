from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.budget.measure import visible_len
from science_tool.budget.registry import BUDGETS
from science_tool.cli import main

REPORT = {
    "validation": [
        {
            "severity": "warning",
            "path": f"p{i}",
            "line": None,
            "rule": "r",
            "task": None,
            "message": "m" * 80,
        }
        for i in range(361)
    ],
    "managed_artifacts": [],
    "unresolved_refs": [],
    "unregistered_ref_kinds": [],
    "lingering_tags_lines": [],
    "agent_context": [],
    "identity_policy": [],
    "entity_identity": [],
    "dataset_anomalies": [],
    "schema_invalid": [],
    "tooling_scaffold": [],
    "accepted_validation": [],
    "unwired_checks": [],
    "legacy_task_type": [],
    "invalid_entity_aspects": [],
    "archive_lag": {"done_in_active": 0, "retired_in_active": 0, "missing_completed": 0},
    # All four LayeredClaimHealthReport keys. The adoption table at health_cli.py:376
    # reads both coverage metrics UNCONDITIONALLY, and the rival-model table reads its
    # list — a fixture carrying only `migration_issues` raises KeyError before any
    # assertion runs.
    "layered_claims": {
        "proposition_claim_layer_coverage": {"numerator": 0, "denominator": 0, "fraction": 0.0},
        "causal_leaning_identification_coverage": {"numerator": 0, "denominator": 0, "fraction": 0.0},
        "rival_model_packets_missing_discriminating_predictions": [],
        "migration_issues": [],
    },
    "cross_paper_evidence": {
        "status": "ok",
        "empty_state": "no_propositions",
        "summary": {},
        "findings": [],
        "propositions": [],
    },
    "prose_epistemics": {
        "applicable": False,
        "summary": {},
        "coverage": {},
        "sources": [],
        "findings": [],
    },
    "total_issues": 361,
}


@pytest.fixture
def stub_report(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_health_report is imported INSIDE health_command, so patch it at its source."""
    import science_tool.graph.health as health_module

    monkeypatch.setattr(health_module, "build_health_report", lambda *_a, **_k: dict(REPORT))


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def test_severity_and_output_options_exist() -> None:
    result = _invoke(["health", "--help"])
    assert result.exit_code == 0, result.output
    assert "--severity" in result.output
    assert "--output" in result.output


def test_table_output_stays_within_budget(stub_report: None) -> None:
    result = _invoke(["health"])
    assert result.exit_code == 0, result.output
    assert visible_len(result.output) <= BUDGETS["health"].max_chars


def test_json_output_stays_within_budget(stub_report: None) -> None:
    result = _invoke(["health", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert visible_len(result.output) <= BUDGETS["health"].max_chars


def test_filtered_report_never_claims_clean(stub_report: None) -> None:
    result = _invoke(["health", "--severity", "error"])
    assert result.exit_code == 0, result.output
    assert "Project is clean" not in result.output
    assert "361" in result.output


def test_table_output_file_is_non_empty_and_complete(stub_report: None, tmp_path: Path) -> None:
    """The defect the previous plan shipped: table + --output wrote nothing."""
    target = tmp_path / "health.txt"
    result = _invoke(["health", "--output", str(target)])
    assert result.exit_code == 0, result.output
    written = target.read_text()
    assert len(written) > BUDGETS["health"].max_chars
    assert written.count("m") >= 361 * 80


def test_json_output_file_is_complete(stub_report: None, tmp_path: Path) -> None:
    target = tmp_path / "health.json"
    result = _invoke(["health", "--format", "json", "--output", str(target)])
    assert result.exit_code == 0, result.output
    payload = json.loads(target.read_text())
    assert len(payload["validation"]) == 361
    assert "section_omitted" not in payload


def test_list_checks_also_routes_through_the_sink(tmp_path: Path) -> None:
    target = tmp_path / "checks.txt"
    result = _invoke(["health", "--list-checks", "--output", str(target)])
    assert result.exit_code == 0, result.output
    assert target.read_text().strip() != ""
