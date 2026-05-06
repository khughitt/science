from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.registry.config import load_global_config


def test_graph_build_in_child_registers_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_dir = tmp_path / "cfg"
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))

    meta = tmp_path / "meta"
    a = tmp_path / "a"
    meta.mkdir()
    a.mkdir()
    (meta / "science.yaml").write_text(
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: {a}
    role: data-source
""",
        encoding="utf-8",
    )
    (a / "science.yaml").write_text(
        f"""
name: a
id: a
role: data-source
parent: {meta}
profile: research
research_question: "..."
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(a)
    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build"])
    assert result.exit_code == 0, result.output

    cfg = load_global_config(cfg_dir / "config.yaml")
    paths = {project.path for project in cfg.projects}
    assert any(path.endswith("/a") for path in paths)
    assert any(path.endswith("/meta") for path in paths)
    child_entry = next(project for project in cfg.projects if project.path.endswith("/a"))
    assert child_entry.role == "data-source"
    assert child_entry.parent and child_entry.parent.endswith("/meta")
