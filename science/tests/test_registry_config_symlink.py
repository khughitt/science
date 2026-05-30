"""Regression tests for symlink-alias project auto-registration (fb-2026-05-30-010).

Invoking `science` from a realpath when the project was registered via a `~`/symlink
alias (or vice versa) must NOT create a second ``projects[]`` entry sharing the same
id, which later breaks ``commons promote`` with "project id is ambiguous".
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.registry.config import (
    GlobalConfig,
    RegisteredProject,
    ensure_registered,
    load_global_config,
    save_global_config,
)


def _make_project(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text("id: cycles\n", encoding="utf-8")


def test_symlink_alias_does_not_duplicate(tmp_path: Path) -> None:
    real_parent = tmp_path / "real"
    real = real_parent / "cycles"
    _make_project(real)

    # alias/ is a symlink to real/, so alias/cycles resolves to real/cycles.
    alias_parent = tmp_path / "alias"
    alias_parent.symlink_to(real_parent)
    alias = alias_parent / "cycles"

    config_path = tmp_path / "config.yaml"

    # Register via the alias first, then via the realpath.
    ensure_registered(alias, "cycles", config_path=config_path, project_id="cycles")
    ensure_registered(real, "cycles", config_path=config_path, project_id="cycles")

    cfg = load_global_config(config_path)
    assert len(cfg.projects) == 1, [p.path for p in cfg.projects]
    # Stored path is normalized to the real path.
    assert cfg.projects[0].path == str(real.resolve())
    assert cfg.projects[0].id == "cycles"


def test_collapses_preexisting_duplicate(tmp_path: Path) -> None:
    real_parent = tmp_path / "real"
    real = real_parent / "cycles"
    _make_project(real)
    alias_parent = tmp_path / "alias"
    alias_parent.symlink_to(real_parent)
    alias = alias_parent / "cycles"

    config_path = tmp_path / "config.yaml"

    # Simulate a config that already accumulated two colliding-id entries: one
    # stored as the realpath, one stored as the symlink-alias path string.
    cfg = GlobalConfig(
        projects=[
            RegisteredProject(path=str(real), name="cycles", registered=date.today(), id="cycles"),
            RegisteredProject(path=str(alias), name="cycles", registered=date.today(), id="cycles"),
        ]
    )
    save_global_config(cfg, config_path)

    ensure_registered(real, "cycles", config_path=config_path, project_id="cycles")

    out = load_global_config(config_path)
    assert len(out.projects) == 1, [p.path for p in out.projects]
    assert out.projects[0].path == str(real.resolve())
