"""`science-tool project artifacts check <name>` verb."""

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def test_check_unknown_artifact_errors() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["project", "artifacts", "check", "nonexistent"])
    assert result.exit_code != 0
    assert "no managed artifact named 'nonexistent'" in result.output


def test_check_human_output_for_missing(tmp_path: Path) -> None:
    """With an empty registry there's nothing to check; this test runs once
    Task 28 lands data/validate.sh. Skip if the registry is empty."""
    from science_tool.project_artifacts import default_registry

    if not default_registry().artifacts:
        return  # nothing to assert
    runner = CliRunner()
    name = default_registry().artifacts[0].name
    result = runner.invoke(main, ["project", "artifacts", "check", name, "--project-root", str(tmp_path)])
    assert result.exit_code == 0
    assert "missing" in result.output.lower()


def test_check_json_output(tmp_path: Path) -> None:
    from science_tool.project_artifacts import default_registry

    if not default_registry().artifacts:
        return
    runner = CliRunner()
    name = default_registry().artifacts[0].name
    result = runner.invoke(
        main,
        ["project", "artifacts", "check", name, "--project-root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["name"] == name
    assert "status" in payload
