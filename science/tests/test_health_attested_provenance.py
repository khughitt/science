from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.health import execute_health_report, expected_producer_ids


def _declared(report) -> frozenset[str]:
    """What ingestion will demand: every producer the report says ran, either way."""
    return frozenset(report.meta.producers_run) | {u.producer_id for u in report.unwired}


@pytest.mark.parametrize(
    "selection",
    [
        {},
        {"fast": True},
        {"checks": frozenset({"managed_artifacts", "tooling_scaffold"})},
        {"checks": frozenset({"entity_identity"})},
        {"skip_checks": frozenset({"validate"})},
    ],
    ids=["full", "fast", "two-source-free", "one-source-requiring", "skip-one"],
)
def test_the_prediction_equals_what_the_report_declares(ungraphed_project: Path, selection):
    """Design §8.1: one full-health fixture cannot kill a literal-list mutation, because a
    list transcribed correctly today matches today's set. Source-free and source-requiring
    selections differ by `schema_invalid`, which appears in neither `--list-checks` nor any
    check's producer id."""
    execution = execute_health_report(
        ungraphed_project,
        ingestion_ref="run:2026-08-02-health-audit-a1b2",
        generated_at="2026-08-02T09:00:00.000000+00:00",
        **selection,
    )

    assert expected_producer_ids(**selection) == _declared(execution.report)


def test_schema_invalid_is_predicted_only_when_sources_load():
    assert "schema_invalid" in expected_producer_ids()
    assert "schema_invalid" not in expected_producer_ids(fast=True)


def test_the_cli_echoes_the_dictated_provenance(ungraphed_project: Path, tmp_path: Path):
    out = tmp_path / "report.json"
    result = CliRunner().invoke(
        main,
        [
            "health", "--project-root", str(ungraphed_project),
            "--format", "json", "--output", str(out),
            "--ingestion-ref", "run:2026-08-02-health-audit-a1b2",
            "--generated-at", "2026-08-02T09:00:00.000000+00:00",
        ],
    )

    assert result.exit_code in (0, 2), result.output
    import json

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ingestion_ref"] == "run:2026-08-02-health-audit-a1b2"
    assert payload["generated_at"] == "2026-08-02T09:00:00.000000+00:00"


def test_the_two_provenance_options_are_required_together(ungraphed_project: Path):
    result = CliRunner().invoke(
        main,
        ["health", "--project-root", str(ungraphed_project), "--ingestion-ref", "run:x"],
    )

    assert result.exit_code != 0
    assert "--generated-at" in result.output
