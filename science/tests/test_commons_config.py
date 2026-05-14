"""Tests for science_tool.commons.config."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.commons.config import (
    CommonsSettings,
    load_data_overrides,
    resolve_commons_data_root,
    resolve_commons_root,
)
from science_tool.commons.errors import CommonsError
from science_tool.registry.config import GlobalConfig, load_global_config, save_global_config


def test_default_settings_root_is_none() -> None:
    assert CommonsSettings().root is None


def test_global_config_includes_commons_with_default() -> None:
    cfg = GlobalConfig()
    assert isinstance(cfg.commons, CommonsSettings)
    assert cfg.commons.root is None


def test_global_config_roundtrip_with_commons(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        yaml.dump(
            {
                "sync": {"stale_after_days": 14},
                "projects": [],
                "commons": {"root": "/tmp/example-commons"},
            }
        ),
        encoding="utf-8",
    )
    cfg = load_global_config(cfg_path)
    assert cfg.commons.root == Path("/tmp/example-commons")
    save_global_config(cfg, cfg_path)
    reloaded = load_global_config(cfg_path)
    assert reloaded.commons.root == Path("/tmp/example-commons")


def test_global_config_missing_commons_block_uses_default(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump({"sync": {"stale_after_days": 14}, "projects": []}), encoding="utf-8")
    cfg = load_global_config(cfg_path)
    assert cfg.commons.root is None


def test_resolve_env_var_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "from-env"))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    assert resolve_commons_root() == tmp_path / "from-env"


def test_resolve_config_used_when_env_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SCIENCE_COMMONS_ROOT", raising=False)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump({"commons": {"root": str(tmp_path / "from-config")}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    assert resolve_commons_root() == tmp_path / "from-config"


def test_resolve_default_when_unset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SCIENCE_COMMONS_ROOT", raising=False)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()  # empty config dir
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    expected = tmp_path / "home" / "d" / "science-commons"
    assert resolve_commons_root() == expected


def test_data_root_default_is_none() -> None:
    assert CommonsSettings().data_root is None


def test_resolve_data_root_env_var_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_DATA_ROOT", str(tmp_path / "from-env"))
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    assert resolve_commons_data_root() == tmp_path / "from-env"


def test_resolve_data_root_config_used_when_env_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SCIENCE_COMMONS_DATA_ROOT", raising=False)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump({"commons": {"data_root": str(tmp_path / "from-config")}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    assert resolve_commons_data_root() == tmp_path / "from-config"


def test_resolve_data_root_default_when_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SCIENCE_COMMONS_DATA_ROOT", raising=False)
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    assert resolve_commons_data_root() == Path("/data/science-commons")


def test_load_data_overrides_missing_file_returns_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    assert load_data_overrides() == {}


def test_load_data_overrides_reads_absolute_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(
        yaml.dump({"cath-domains": "/data/legacy/cath"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    assert load_data_overrides() == {"cath-domains": Path("/data/legacy/cath")}


def test_load_data_overrides_rejects_relative_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(
        yaml.dump({"cath-domains": "legacy/cath"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    with pytest.raises(CommonsError, match="absolute"):
        load_data_overrides()


def test_load_data_overrides_rejects_non_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(yaml.dump(["not", "a", "mapping"]), encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    with pytest.raises(CommonsError, match="mapping"):
        load_data_overrides()


def test_load_data_overrides_rejects_malformed_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text("cath-domains: [unclosed\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    with pytest.raises(CommonsError, match="malformed YAML"):
        load_data_overrides()


def test_load_data_overrides_rejects_non_string_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(yaml.dump({"cath-domains": 123}), encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    with pytest.raises(CommonsError):
        load_data_overrides()
