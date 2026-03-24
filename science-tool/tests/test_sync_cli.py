from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _setup_projects(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create two minimal projects and a config."""
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    for proj, name in [(proj_a, "proj-a"), (proj_b, "proj-b")]:
        proj.mkdir()
        (proj / "science.yaml").write_text(f"name: {name}\nknowledge_profiles:\n  local: local\n")
        for d in ("doc", "specs", "tasks", "knowledge"):
            (proj / d).mkdir()

    config_path = tmp_path / "config.yaml"
    return proj_a, proj_b, config_path


def test_sync_status_no_config(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["sync", "status", "--config", str(tmp_path / "missing.yaml")])
    assert result.exit_code == 0
    assert "No sync" in result.output or "never" in result.output.lower()


def test_sync_projects_list(tmp_path):
    from science_tool.registry.config import ensure_registered

    config_path = tmp_path / "config.yaml"
    ensure_registered(tmp_path / "proj-a", "proj-a", config_path)
    runner = CliRunner()
    result = runner.invoke(main, ["sync", "projects", "--config", str(config_path)])
    assert result.exit_code == 0
    assert "proj-a" in result.output
