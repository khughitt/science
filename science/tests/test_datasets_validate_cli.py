"""CLI behaviour for `science datasets validate` descriptor-target dispatch."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _pkg_dir(tmp_path: Path, pkg: dict, csv: str = "a\n1\n") -> Path:
    d = tmp_path / "pkg"
    d.mkdir(parents=True, exist_ok=True)
    (d / "x.csv").write_text(csv)
    (d / "datapackage.json").write_text(json.dumps(pkg))
    return d


def test_valid_package_dir_exits_zero(tmp_path: Path) -> None:
    pkg = {"name": "p", "resources": [
        {"name": "x", "path": "x.csv",
         "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}
    res = CliRunner().invoke(main, ["datasets", "validate", "--path", str(_pkg_dir(tmp_path, pkg))])
    assert res.exit_code == 0, res.output


def test_invalid_package_dir_exits_nonzero(tmp_path: Path) -> None:
    pkg = {"name": "p", "resources": [
        {"name": "x", "path": "x.csv",
         "schema": {"fields": [{"name": "a", "type": "string", "qa": {"low_variance": True}}]}}]}
    res = CliRunner().invoke(main, ["datasets", "validate", "--path", str(_pkg_dir(tmp_path, pkg))])
    assert res.exit_code != 0, res.output


def test_empty_dir_exits_nonzero(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    res = CliRunner().invoke(main, ["datasets", "validate", "--path", str(empty)])
    # An explicit target with no descriptor must fail, not warn-and-pass.
    assert res.exit_code != 0, res.output


def test_legacy_raw_scan_still_works(tmp_path: Path) -> None:
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    (raw / "x.csv").write_text("a\n1\n")
    (raw / "datapackage.json").write_text(json.dumps(
        {"name": "p", "resources": [
            {"name": "x", "path": "x.csv",
             "schema": {"fields": [{"name": "a", "type": "integer"}]}}]}))
    res = CliRunner().invoke(main, ["datasets", "validate", "--path", str(tmp_path / "data")])
    assert res.exit_code == 0, res.output
