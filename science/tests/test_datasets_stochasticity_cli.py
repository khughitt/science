from __future__ import annotations

import json

from click.testing import CliRunner

from science_tool.cli import main


def test_human_output_names_run_and_steps(registrable_run_project):
    project_root, dataset_id = registrable_run_project
    result = CliRunner().invoke(
        main, ["dataset", "stochasticity", dataset_id, "--project-root", str(project_root)]
    )
    assert result.exit_code == 0, result.output
    assert "run:" in result.output
    assert "nondeterministic" in result.output


def test_json_output_is_machine_readable(registrable_run_project):
    project_root, dataset_id = registrable_run_project
    result = CliRunner().invoke(
        main,
        ["dataset", "stochasticity", dataset_id, "--project-root", str(project_root), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["run_id"] is not None
    assert isinstance(payload["stochastic_steps"], list)


def test_unknown_dataset_exits_nonzero(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "id: project:x\nname: X\nprofile: software\n", encoding="utf-8"
    )
    result = CliRunner().invoke(
        main, ["dataset", "stochasticity", "dataset:nope", "--project-root", str(tmp_path)]
    )
    assert result.exit_code == 1
