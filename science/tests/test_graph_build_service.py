"""Characterization tests for `science_tool.graph.build.build_project_graph`.

Locks in that the CLI-facing wrapper — not `materialize_graph` itself — owns
the registration side-effect (Convergence Phase 4, Task 4 push-down).
"""

from __future__ import annotations

from pathlib import Path

from science_tool.graph.build import LocalGraphBuild, build_project_graph
from science_tool.graph.materialize import materialize_graph
from science_tool.registry.config import load_global_config


def _seed_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: proj\nid: proj\nrole: standalone\n",
        encoding="utf-8",
    )


def test_build_project_graph_registers_unregistered_project(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "isolated-config"
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(config_dir))

    project_root = tmp_path / "proj"
    project_root.mkdir()
    _seed_project(project_root)

    result = build_project_graph(project_root)

    assert isinstance(result, LocalGraphBuild)
    assert result.local_path == project_root / "knowledge" / "graph.trig"
    assert result.local_path.is_file()
    assert result.config is not None
    assert result.config.name == "proj"

    cfg = load_global_config(config_dir / "config.yaml")
    assert len(cfg.projects) == 1
    assert cfg.projects[0].path == str(project_root.resolve())


def test_direct_materialize_graph_does_not_register(tmp_path, monkeypatch) -> None:
    config_dir = tmp_path / "isolated-config"
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(config_dir))

    project_root = tmp_path / "proj"
    project_root.mkdir()
    _seed_project(project_root)

    local_path = materialize_graph(project_root)

    assert local_path == project_root / "knowledge" / "graph.trig"
    assert local_path.is_file()
    # No registry file was ever written — materialize_graph has no registration side-effect.
    assert not (config_dir / "config.yaml").exists()
