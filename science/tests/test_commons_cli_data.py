"""Tests for the `science commons data` CLI subgroup."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from science_tool.commons.cli import commons_group

FIXTURES = Path(__file__).parent / "fixtures" / "commons"
_SLUG = "rnaseq-example"
_LOGICAL = "counts.parquet"
_CONTENT = b"counts-data\n"


def _setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, write_data: bool = True
) -> None:
    """Build a commons store + data root and point the env at them."""
    commons_root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", commons_root)
    digest = hashlib.sha256(_CONTENT).hexdigest()
    dp = commons_root / "datasets" / _SLUG / "datapackage.yaml"
    dp.write_text(
        yaml.dump(
            {
                "name": _SLUG,
                "profile": "data-package",
                "resources": [
                    {"name": "counts", "path": _LOGICAL, "hash": f"sha256:{digest}"}
                ],
            }
        ),
        encoding="utf-8",
    )
    data_root = tmp_path / "data"
    if write_data:
        target = data_root / _SLUG / _LOGICAL
        target.parent.mkdir(parents=True)
        target.write_bytes(_CONTENT)
    data_root.mkdir(exist_ok=True)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(data_root))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))


def test_data_resolve_plain_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(commons_group, ["data", "resolve", f"dataset:{_SLUG}", _LOGICAL])
    assert result.exit_code == 0, result.output
    printed = Path(result.output.strip())
    assert printed == (tmp_path / "data" / _SLUG / _LOGICAL).resolve()


def test_data_resolve_json_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(
        commons_group, ["data", "resolve", f"dataset:{_SLUG}", _LOGICAL, "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dataset_id"] == f"dataset:{_SLUG}"
    assert payload["logical_path"] == _LOGICAL
    assert payload["source"] == "data_root"
    assert payload["hash"] == f"sha256:{hashlib.sha256(_CONTENT).hexdigest()}"
    assert payload["resolved_path"] == str((tmp_path / "data" / _SLUG / _LOGICAL).resolve())


def test_data_resolve_format_json_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(
        commons_group, ["data", "resolve", f"dataset:{_SLUG}", _LOGICAL, "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dataset_id"] == f"dataset:{_SLUG}"
    assert payload["logical_path"] == _LOGICAL
    assert payload["source"] == "data_root"


def test_data_resolve_not_found_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch, write_data=False)
    runner = CliRunner()
    result = runner.invoke(commons_group, ["data", "resolve", f"dataset:{_SLUG}", _LOGICAL])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_data_resolve_hostile_path_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(
        commons_group, ["data", "resolve", f"dataset:{_SLUG}", "../../etc/passwd"]
    )
    assert result.exit_code != 0
    assert "invalid logical path" in result.output


def test_data_resolve_non_dataset_id_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(commons_group, ["data", "resolve", "paper:Adams2025", _LOGICAL])
    assert result.exit_code != 0
    assert "dataset" in result.output


def test_data_resolve_missing_datapackage_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, monkeypatch)
    (tmp_path / "commons" / "datasets" / _SLUG / "datapackage.yaml").unlink()
    runner = CliRunner()
    result = runner.invoke(commons_group, ["data", "resolve", f"dataset:{_SLUG}", _LOGICAL])
    assert result.exit_code != 0
    assert "datapackage.yaml" in result.output
