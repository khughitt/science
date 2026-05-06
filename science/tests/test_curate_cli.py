from __future__ import annotations

import json

from click.testing import CliRunner

from science_tool.cli import main


def test_curate_group_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["curate", "--help"])
    assert result.exit_code == 0
    assert "inventory" in result.output


def test_curate_inventory_outputs_json() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["curate", "inventory", "--project-root", ".", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["project_root"] == "."
    assert "artifact_counts" in payload
