from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.skills_lint.cli import skills_group


def _enrolled_project(root: Path) -> None:
    from _fixtures.entity_helpers import seed_project

    root.mkdir()
    seed_project(root)
    cfg = root / "science.yaml"
    cfg.write_text(
        cfg.read_text()
        + "\nentity_schema_version: 3\nskill_coverage:\n  domains:\n    molecular-measurement: enrolled\n",
        encoding="utf-8",
    )


def _registry(tmp_path: Path, entries: list[dict]) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"projects": entries}), encoding="utf-8")
    return config_path


def test_coverage_cli_stdout_json(tmp_path: Path, monkeypatch) -> None:
    enrolled = tmp_path / "enrolled"
    _enrolled_project(enrolled)
    # SCIENCE_CONFIG_DIR -> get_default_config_path() == tmp_path/config.yaml, which _registry writes.
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path))
    _registry(
        tmp_path,
        [
            {
                "path": str(enrolled),
                "name": "enrolled",
                "id": "enrolled",
                "registered": "2026-07-25",
            },
        ],
    )
    runner = CliRunner()
    result = runner.invoke(skills_group, ["coverage"])
    assert result.exit_code == 0, result.output
    obj = json.loads(result.output)
    assert obj["scope"]["mode"] == "portfolio"


def test_coverage_cli_output_file_and_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path))
    _registry(tmp_path, [])  # empty registry -> hard error
    out = tmp_path / "report.json"
    out.write_text("PRIOR", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(skills_group, ["coverage", "--output", str(out)])
    assert result.exit_code != 0  # empty registry -> hard error
    assert out.read_text(encoding="utf-8") == "PRIOR"  # untouched on failure
