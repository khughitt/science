"""Tests for science_tool.commons.config."""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
import yaml

from science_tool.commons.config import (
    CommonsSettings,
    check_override_conflict,
    load_data_overrides,
    resolve_commons_data_root,
    resolve_commons_root,
    resolve_project_by_id,
    restore_data_override_from_backup,
    upsert_data_override,
)
from science_tool.commons.errors import CommonsError, PromoteOverrideConflictError
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


def test_load_data_overrides_rejects_duplicate_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(
        "cath-domains: /data/one\ncath-domains: /data/two\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    with pytest.raises(CommonsError, match="duplicate key"):
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


def test_load_data_overrides_wraps_read_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    data_yaml = cfg_dir / "data.yaml"
    data_yaml.write_text(yaml.dump({"cath-domains": "/data/legacy/cath"}), encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    original_read_text = Path.read_text

    def fail_for_data_yaml(self: Path, *args: Any, **kwargs: Any) -> str:
        if self == data_yaml:
            raise OSError("permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_for_data_yaml)
    with pytest.raises(CommonsError, match="cannot read data overrides") as exc_info:
        load_data_overrides()

    assert exc_info.value.__cause__ is not None


def test_load_data_overrides_rejects_non_string_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(yaml.dump({"cath-domains": 123}), encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    with pytest.raises(CommonsError):
        load_data_overrides()


def test_upsert_data_override_creates_file_when_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    backup_path = upsert_data_override(
        slug="x",
        absolute_path=tmp_path / "fakedata",
        op_id="op123",
    )

    yaml_path = cfg_dir / "data.yaml"
    assert backup_path == cfg_dir / "data.yaml.bak.op123"
    assert yaml_path.is_file()
    assert yaml.safe_load(yaml_path.read_text(encoding="utf-8")) == {
        "x": str(tmp_path / "fakedata")
    }
    assert (cfg_dir / "data.yaml.bak.op123.absent").is_file()
    assert not backup_path.exists()


def test_restore_data_override_removes_file_when_absent_sentinel_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    upsert_data_override(
        slug="x",
        absolute_path=tmp_path / "fakedata",
        op_id="opABS",
    )
    assert (cfg_dir / "data.yaml").is_file()

    restore_data_override_from_backup(op_id="opABS")

    assert not (cfg_dir / "data.yaml").exists()
    assert not (cfg_dir / "data.yaml.bak.opABS.absent").exists()


def test_upsert_data_override_preserves_existing_entries_and_exact_backup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    yaml_path = cfg_dir / "data.yaml"
    previous_content = "other: /other/path\n"
    yaml_path.write_text(previous_content, encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    upsert_data_override(slug="x", absolute_path=tmp_path / "newdata", op_id="op999")

    assert yaml.safe_load(yaml_path.read_text(encoding="utf-8")) == {
        "other": "/other/path",
        "x": str(tmp_path / "newdata"),
    }
    assert (cfg_dir / "data.yaml.bak.op999").read_bytes() == previous_content.encode()


def test_check_override_conflict_raises_on_mismatch_and_allows_same_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text("x: /existing/path\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    with pytest.raises(PromoteOverrideConflictError) as exc_info:
        check_override_conflict(slug="x", planned_path=tmp_path / "different")

    assert exc_info.value.slug == "x"
    assert exc_info.value.existing_path == Path("/existing/path")
    assert exc_info.value.planned_path == tmp_path / "different"
    check_override_conflict(slug="x", planned_path=Path("/existing/path"))


def test_restore_data_override_from_normal_backup_restores_exact_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    yaml_path = cfg_dir / "data.yaml"
    bak_path = cfg_dir / "data.yaml.bak.opABC"
    before_content = b"before: state\n# exact\n"
    bak_path.write_bytes(before_content)
    yaml_path.write_text("after: state\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    restore_data_override_from_backup(op_id="opABC")

    assert yaml_path.read_bytes() == before_content
    assert not bak_path.exists()


def test_restore_data_override_from_backup_rejects_missing_backup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    with pytest.raises(CommonsError, match="backup not found"):
        restore_data_override_from_backup(op_id="missing")


def test_upsert_data_override_rejects_relative_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))

    with pytest.raises(CommonsError, match="absolute"):
        upsert_data_override(
            slug="x",
            absolute_path=Path("relative/path"),
            op_id="opREL",
        )


def test_upsert_data_override_rejects_existing_non_mapping_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text("- not\n- mapping\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    with pytest.raises(CommonsError, match="mapping"):
        upsert_data_override(
            slug="x",
            absolute_path=tmp_path / "fakedata",
            op_id="opBADMAP",
        )
    assert not (cfg_dir / "data.yaml.bak.opBADMAP").exists()


def test_upsert_data_override_rejects_existing_non_string_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text("x: 123\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    with pytest.raises(CommonsError, match="string slug"):
        upsert_data_override(
            slug="y",
            absolute_path=tmp_path / "fakedata",
            op_id="opBADVALUE",
        )


def test_upsert_data_override_rejects_existing_relative_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text("x: relative/path\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    with pytest.raises(CommonsError, match="absolute"):
        upsert_data_override(
            slug="y",
            absolute_path=tmp_path / "fakedata",
            op_id="opBADREL",
        )


def test_upsert_data_override_rejects_existing_duplicate_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text(
        "x: /data/one\nx: /data/two\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    with pytest.raises(CommonsError, match="duplicate key"):
        upsert_data_override(
            slug="y",
            absolute_path=tmp_path / "fakedata",
            op_id="opDUP",
        )
    assert not (cfg_dir / "data.yaml.bak.opDUP").exists()


def test_upsert_data_override_rejects_data_yaml_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").mkdir()
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    with pytest.raises(CommonsError, match="expected a file"):
        upsert_data_override(
            slug="x",
            absolute_path=tmp_path / "fakedata",
            op_id="opDIR",
        )
    assert not (cfg_dir / "data.yaml.bak.opDIR.absent").exists()


def test_check_override_conflict_expands_existing_user_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    home = tmp_path / "home"
    cfg_dir.mkdir()
    home.mkdir()
    (cfg_dir / "data.yaml").write_text("x: ~/data/x\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("HOME", str(home))

    check_override_conflict(slug="x", planned_path=home / "data" / "x")


def test_upsert_data_override_rejects_reused_op_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").write_text("x: /existing/path\n", encoding="utf-8")
    (cfg_dir / "data.yaml.bak.opREUSE").write_text("before\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    with pytest.raises(CommonsError, match="backup already exists"):
        upsert_data_override(
            slug="y",
            absolute_path=tmp_path / "fakedata",
            op_id="opREUSE",
        )


def test_restore_data_override_from_backup_rejects_ambiguous_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml.bak.opAMB").write_text("before\n", encoding="utf-8")
    (cfg_dir / "data.yaml.bak.opAMB.absent").write_text("", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    with pytest.raises(CommonsError, match="ambiguous"):
        restore_data_override_from_backup(op_id="opAMB")


def test_restore_data_override_from_backup_rejects_data_yaml_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "data.yaml").mkdir()
    (cfg_dir / "data.yaml.bak.opDIR.absent").write_text("", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    with pytest.raises(CommonsError, match="expected a file"):
        restore_data_override_from_backup(op_id="opDIR")


def test_resolve_project_root_returns_registered_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from science_tool.commons.config import resolve_project_root

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump(
            {
                "projects": [
                    {
                        "path": "/home/me/d/protein-landscape",
                        "name": "protein-landscape",
                        "registered": "2026-05-14",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    assert resolve_project_root("protein-landscape") == Path(
        "/home/me/d/protein-landscape"
    )


def test_resolve_project_root_unknown_name_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from science_tool.commons.config import resolve_project_root
    from science_tool.commons.errors import ProjectNotRegisteredError

    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump({"projects": []}), encoding="utf-8"
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    with pytest.raises(ProjectNotRegisteredError, match="nope"):
        resolve_project_root("nope")


def _write_config(tmp_path: Path, body: str) -> Path:
    """Write a config.yaml under tmp_path/.science-config/ and return that dir."""
    cfg_dir = tmp_path / ".science-config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg = cfg_dir / "config.yaml"
    cfg.write_text(dedent(body), encoding="utf-8")
    return cfg_dir


def test_resolve_project_by_id_returns_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = _write_config(
        tmp_path,
        """
        projects:
          - path: ~/d/natural-systems
            name: natural-systems-guide
            id: natural-systems
            role: standalone
            parent: null
            registered: "2026-01-01"
        """,
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("HOME", str(tmp_path))
    p = resolve_project_by_id("natural-systems")
    assert p == (tmp_path / "d" / "natural-systems")


def test_resolve_project_by_id_rejects_unregistered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = _write_config(
        tmp_path,
        """
        projects:
          - path: ~/d/natural-systems
            name: natural-systems-guide
            id: natural-systems
            role: standalone
            parent: null
            registered: "2026-01-01"
        """,
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(CommonsError, match="no registered project with id"):
        resolve_project_by_id("not-a-real-id")


def test_resolve_project_by_id_rejects_null_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = _write_config(
        tmp_path,
        """
        projects:
          - path: ~/d/legacy
            name: legacy-project
            id: null
            role: null
            parent: null
            registered: "2026-01-01"
        """,
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(CommonsError, match="id: null"):
        resolve_project_by_id("legacy-project")
