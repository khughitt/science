from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main


class _File:
    filename = "x.csv"
    format = "csv"
    size_bytes = 1
    checksum = None


class _Adapter:
    def __init__(self) -> None:
        self.destinations: list[Path] = []

    def files(self, dataset_id: str) -> list[_File]:
        assert dataset_id == "abc"
        return [_File()]

    def download(self, file_info: _File, dest_dir: Path) -> Path:
        self.destinations.append(dest_dir)
        return dest_dir / file_info.filename


def _write_project(root: Path, extra: dict | None = None) -> None:
    payload = {"name": "Demo", "id": "demo"}
    if extra:
        payload.update(extra)
    (root / "science.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")


def _write_datapackage(root: Path) -> None:
    raw = root / "raw"
    raw.mkdir(parents=True)
    (raw / "x.csv").write_text("a\n1\n", encoding="utf-8")
    (raw / "datapackage.json").write_text(
        json.dumps(
            {
                "name": "p",
                "resources": [{"name": "x", "path": "x.csv", "schema": {"fields": [{"name": "a", "type": "integer"}]}}],
            }
        ),
        encoding="utf-8",
    )


def test_download_default_uses_project_data_raw(monkeypatch, tmp_path: Path) -> None:
    _write_project(tmp_path)
    adapter = _Adapter()
    monkeypatch.setattr("science_tool.cli.get_adapter", lambda source: adapter)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    result = CliRunner().invoke(
        main,
        ["datasets", "download", "--project-root", str(tmp_path), "zenodo:abc"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert adapter.destinations == [tmp_path.resolve() / "data" / "raw"]


def test_download_default_uses_configured_project_root(monkeypatch, tmp_path: Path) -> None:
    bulk = tmp_path / "bulk"
    _write_project(tmp_path, {"data": {"root": str(bulk)}})
    adapter = _Adapter()
    monkeypatch.setattr("science_tool.cli.get_adapter", lambda source: adapter)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    result = CliRunner().invoke(
        main,
        ["datasets", "download", "--project-root", str(tmp_path), "zenodo:abc"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert adapter.destinations == [bulk / "raw"]


def test_download_from_subdirectory_discovers_project_root(monkeypatch, tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    _write_project(tmp_path)
    adapter = _Adapter()
    monkeypatch.setattr("science_tool.cli.get_adapter", lambda source: adapter)
    monkeypatch.chdir(nested)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    result = CliRunner().invoke(main, ["datasets", "download", "zenodo:abc"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert adapter.destinations == [tmp_path.resolve() / "data" / "raw"]


def test_download_explicit_dest_is_used_verbatim(monkeypatch, tmp_path: Path) -> None:
    _write_project(tmp_path, {"data": {"root": str(tmp_path / "bulk")}})
    explicit = tmp_path / "chosen"
    adapter = _Adapter()
    monkeypatch.setattr("science_tool.cli.get_adapter", lambda source: adapter)
    result = CliRunner().invoke(
        main,
        ["datasets", "download", "--project-root", str(tmp_path), "--dest", str(explicit), "zenodo:abc"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert adapter.destinations == [explicit]


def test_validate_default_uses_configured_data_root(monkeypatch, tmp_path: Path) -> None:
    bulk = tmp_path / "bulk"
    _write_project(tmp_path, {"data": {"root": str(bulk)}})
    _write_datapackage(bulk)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    result = CliRunner().invoke(
        main,
        ["datasets", "validate", "--project-root", str(tmp_path)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
