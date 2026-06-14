# science/tests/test_infer_schema_cli.py
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import datasets


def _pkg(tmp_path: Path) -> Path:
    (tmp_path / "obs.csv").write_text("id,val\nA,1.5\nB,2.5\n")
    dp = tmp_path / "datapackage.json"
    dp.write_text(json.dumps({"name": "p", "resources": [{"name": "obs", "path": "obs.csv"}]}))
    return dp


def test_cli_readonly_does_not_mutate(tmp_path: Path) -> None:
    dp = _pkg(tmp_path)
    before = dp.read_text()
    result = CliRunner().invoke(datasets, ["infer-schema", str(dp), "--resource", "obs"])
    assert result.exit_code == 0, result.output
    assert dp.read_text() == before
    assert "val" in result.output


def test_cli_write_applies_patch(tmp_path: Path) -> None:
    dp = _pkg(tmp_path)
    result = CliRunner().invoke(datasets, ["infer-schema", str(dp), "--resource", "obs", "--write"])
    assert result.exit_code == 0, result.output
    fields = json.loads(dp.read_text())["resources"][0]["schema"]["fields"]
    assert {f["name"] for f in fields} == {"id", "val"}


def test_cli_emit_suggestions_writes_yaml_only(tmp_path: Path) -> None:
    dp = _pkg(tmp_path)
    out = tmp_path / "sugg.yaml"
    before = dp.read_text()
    result = CliRunner().invoke(
        datasets, ["infer-schema", str(dp), "--resource", "obs", "--emit-suggestions", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert dp.read_text() == before  # descriptor untouched


def test_cli_unknown_resource_errors(tmp_path: Path) -> None:
    dp = _pkg(tmp_path)
    result = CliRunner().invoke(datasets, ["infer-schema", str(dp), "--resource", "nope"])
    assert result.exit_code != 0
    assert "no resource" in result.output.lower()


def test_cli_json_format(tmp_path: Path) -> None:
    dp = _pkg(tmp_path)
    result = CliRunner().invoke(
        datasets, ["infer-schema", str(dp), "--resource", "obs", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert '"patch"' in result.output
