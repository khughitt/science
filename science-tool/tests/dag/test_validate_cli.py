"""Click-runner tests for `science-tool dag validate` + `dag schema`."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.dag.cli import dag_group


def test_schema_stdout_is_valid_json() -> None:
    runner = CliRunner()
    result = runner.invoke(dag_group, ["schema"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data.get("title") == "EdgesYamlFile"


def test_schema_write_to_file(tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "s.json"
    result = runner.invoke(dag_group, ["schema", "--output", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data.get("title") == "EdgesYamlFile"
