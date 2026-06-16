from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from click.testing import CliRunner

from science_tool.cli import main


def _pkg(tmp_path: Path, *, minimum: int | None = None) -> Path:
    d = tmp_path / "pkg"
    d.mkdir()
    pd.DataFrame({"p": [-1.0, 1.0]}).to_parquet(d / "a.parquet")
    constraints = f"          constraints: {{minimum: {minimum}}}\n" if minimum is not None else ""
    (d / "datapackage.yaml").write_text(
        "name: p\nresources:\n"
        "  - name: a\n    path: a.parquet\n    schema:\n      fields:\n"
        "        - name: p\n          type: number\n" + constraints)
    return d


def test_cli_clean_exits_zero(tmp_path):
    res = CliRunner().invoke(main, ["datasets", "qa", str(_pkg(tmp_path))])
    assert res.exit_code == 0, res.output
    assert "package: ok" in res.output


def test_cli_structural_exits_one(tmp_path):
    res = CliRunner().invoke(main, ["datasets", "qa", str(_pkg(tmp_path, minimum=0))])
    assert res.exit_code == 1
    assert "package: FAIL" in res.output


def test_cli_no_strict_exits_zero(tmp_path):
    res = CliRunner().invoke(main, ["datasets", "qa", str(_pkg(tmp_path, minimum=0)), "--no-strict"])
    assert res.exit_code == 0


def test_cli_bad_path_exits_two(tmp_path):
    res = CliRunner().invoke(main, ["datasets", "qa", str(tmp_path / "nope")])
    assert res.exit_code == 2


def test_cli_json_format_is_rollup(tmp_path):
    res = CliRunner().invoke(main, ["datasets", "qa", str(_pkg(tmp_path, minimum=0)), "--format", "json"])
    payload = json.loads(res.output)
    assert payload["package_structural_failed"] is True
    assert payload["resources"][0]["resource"] == "a"


def test_cli_report_dir_persists(tmp_path):
    out = tmp_path / "out"
    res = CliRunner().invoke(main, ["datasets", "qa", str(_pkg(tmp_path, minimum=0)),
                                    "--report-dir", str(out)])
    assert res.exit_code == 1
    assert (out / "qa_report.json").exists() and (out / "a" / "qa_report.json").exists()
