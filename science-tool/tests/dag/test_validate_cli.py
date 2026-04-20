"""Click-runner tests for `science-tool dag validate` + `dag schema`."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.dag.cli import dag_group

FIXTURE_MINIMAL = Path(__file__).parent / "fixtures" / "minimal"
FIXTURE_MM30 = Path(__file__).parent / "fixtures" / "mm30"


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


def test_validate_clean_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(
        dag_group,
        ["validate", "--project", str(FIXTURE_MINIMAL / "clean")],
    )
    assert result.exit_code == 0


def test_validate_cyclic_exits_one() -> None:
    runner = CliRunner()
    result = runner.invoke(
        dag_group,
        ["validate", "--project", str(FIXTURE_MINIMAL / "cyclic")],
    )
    assert result.exit_code == 1
    assert "acyclicity" in result.output


def test_validate_missing_identification_non_strict_exits_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(
        dag_group,
        ["validate", "--project", str(FIXTURE_MINIMAL / "missing-identification")],
    )
    assert result.exit_code == 0


def test_validate_missing_identification_strict_exits_one() -> None:
    runner = CliRunner()
    result = runner.invoke(
        dag_group,
        [
            "validate",
            "--strict",
            "--project",
            str(FIXTURE_MINIMAL / "missing-identification"),
        ],
    )
    assert result.exit_code == 1
    assert "identification_missing" in result.output


def test_validate_json_shape() -> None:
    runner = CliRunner()
    result = runner.invoke(
        dag_group,
        [
            "validate",
            "--json",
            "--project",
            str(FIXTURE_MINIMAL / "clean"),
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True
    assert data["strict"] is False
    assert data["findings"] == []


def test_validate_dag_scope() -> None:
    # The mm30 fixture has 4 DAGs. --dag h1-h2-bridge restricts to one.
    runner = CliRunner()
    result = runner.invoke(
        dag_group,
        [
            "validate",
            "--dag",
            "h1-h2-bridge",
            "--project",
            str(FIXTURE_MM30),
        ],
    )
    assert result.exit_code == 0
