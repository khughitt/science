"""Tests for science_tool.commons.resolver."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
import yaml

from science_tool.commons.errors import (
    CommonsDatapackageError,
    CommonsEntityError,
    CommonsLayoutError,
    DataIntegrityError,
    DataLogicalPathError,
    DataResourceNotFoundError,
)
from science_tool.commons.resolver import ResolvedDataResource, resolve

FIXTURES = Path(__file__).parent / "fixtures" / "commons"
_SLUG = "rnaseq-example"
_LOGICAL = "counts.parquet"
_CONTENT = b"counts-data\n"


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point SCIENCE_CONFIG_DIR at an isolated dir so load_data_overrides() does
    not read the developer's real ~/.config/science/data.yaml. Tests that need a
    data.yaml write it into `tmp_path / "cfg"`."""
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))


def _make_commons(tmp_path: Path, *, content: bytes = _CONTENT) -> Path:
    """Copy the valid fixture store into tmp_path and rewrite the rnaseq-example
    datapackage.yaml so its single resource points at `_LOGICAL` with the real
    sha256 of `content`. Returns the commons root."""
    commons_root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", commons_root)
    digest = hashlib.sha256(content).hexdigest()
    dp = commons_root / "datasets" / _SLUG / "datapackage.yaml"
    dp.write_text(
        yaml.dump(
            {
                "name": _SLUG,
                "profile": "data-package",
                "resources": [{"name": "counts", "path": _LOGICAL, "hash": f"sha256:{digest}"}],
            }
        ),
        encoding="utf-8",
    )
    return commons_root


def _write_data(root: Path, content: bytes = _CONTENT) -> Path:
    """Write <root>/<slug>/<logical> with `content` -- the data_root layout.
    Returns the file path."""
    target = root / _SLUG / _LOGICAL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def _write_override_data(override_dir: Path, content: bytes = _CONTENT) -> Path:
    """Write <override_dir>/<logical> with `content`. The per-machine override
    maps a slug straight to its dataset directory, so bytes live directly under
    it -- no <slug>/ segment. Returns the file path."""
    override_dir.mkdir(parents=True, exist_ok=True)
    target = override_dir / _LOGICAL
    target.write_bytes(content)
    return target


def test_resolve_from_data_root(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    target = _write_data(data_root)
    result = resolve(f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root)
    assert isinstance(result, ResolvedDataResource)
    assert result.path == target.resolve()
    assert result.source == "data_root"
    assert result.logical_path == _LOGICAL
    assert result.dataset_id == f"dataset:{_SLUG}"
    assert result.hash == f"sha256:{hashlib.sha256(_CONTENT).hexdigest()}"


def test_resolve_from_override(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"  # intentionally empty
    override_dir = tmp_path / "legacy"
    override_target = _write_override_data(override_dir)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(yaml.dump({_SLUG: str(override_dir)}), encoding="utf-8")
    result = resolve(f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root)
    assert result.path == override_target.resolve()
    assert result.source == "override"


def test_resolve_data_root_takes_precedence_over_override(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    data_target = _write_data(data_root)
    override_dir = tmp_path / "legacy"
    _write_override_data(override_dir)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(yaml.dump({_SLUG: str(override_dir)}), encoding="utf-8")
    result = resolve(f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root)
    assert result.path == data_target.resolve()
    assert result.source == "data_root"


def test_resolve_data_root_ignores_malformed_override_config(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    data_target = _write_data(data_root)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text("[not-valid-yaml", encoding="utf-8")
    result = resolve(f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root)
    assert result.path == data_target.resolve()
    assert result.source == "data_root"


def test_resolve_not_found(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"  # nothing written
    with pytest.raises(DataResourceNotFoundError):
        resolve(f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root)


def test_resolve_hash_mismatch(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    _write_data(data_root, content=b"corrupted-bytes\n")
    with pytest.raises(DataIntegrityError):
        resolve(f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root)


def test_resolve_rejects_non_dataset_id(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    with pytest.raises(CommonsEntityError):
        resolve("paper:Adams2025", _LOGICAL, commons_root=commons_root, data_root=data_root)


def test_resolve_rejects_hostile_dataset_id_before_adapter_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"

    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("adapter load should not be called for malformed dataset ids")

    monkeypatch.setattr("science_tool.commons.resolver.CommonsEntityAdapter.load", fail_if_called)
    with pytest.raises(CommonsEntityError):
        resolve("dataset:../../escape", _LOGICAL, commons_root=commons_root, data_root=data_root)


@pytest.mark.parametrize("dataset_id", ["dataset:RNAseq-example", "dataset:a"])
def test_resolve_rejects_invalid_dataset_schema_ids_before_adapter_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dataset_id: str
) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"

    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("adapter load should not be called for malformed dataset ids")

    monkeypatch.setattr("science_tool.commons.resolver.CommonsEntityAdapter.load", fail_if_called)
    with pytest.raises(CommonsEntityError):
        resolve(dataset_id, _LOGICAL, commons_root=commons_root, data_root=data_root)


def test_resolve_rejects_hostile_logical_path(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    with pytest.raises(DataLogicalPathError):
        resolve(
            f"dataset:{_SLUG}",
            "../../etc/passwd",
            commons_root=commons_root,
            data_root=data_root,
        )


def test_resolve_missing_logical_path_in_descriptor(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    with pytest.raises(CommonsDatapackageError, match="no resource"):
        resolve(
            f"dataset:{_SLUG}",
            "not-in-descriptor.tsv",
            commons_root=commons_root,
            data_root=data_root,
        )


def test_resolve_missing_datapackage_raises_layout_error(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    (commons_root / "datasets" / _SLUG / "datapackage.yaml").unlink()
    data_root = tmp_path / "data"
    with pytest.raises(CommonsLayoutError):
        resolve(f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root)


def test_resolve_directory_at_target_is_not_resolved(tmp_path: Path) -> None:
    commons_root = _make_commons(tmp_path)
    data_root = tmp_path / "data"
    # A directory sits where the resource file should be.
    (data_root / _SLUG / _LOGICAL).mkdir(parents=True)
    with pytest.raises(DataResourceNotFoundError):
        resolve(f"dataset:{_SLUG}", _LOGICAL, commons_root=commons_root, data_root=data_root)
