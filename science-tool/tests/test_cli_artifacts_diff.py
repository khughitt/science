"""`science-tool project artifacts diff <name>` verb."""

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def test_diff_unknown_artifact_errors() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["project", "artifacts", "diff", "nonexistent"])
    assert result.exit_code != 0


def test_diff_against_missing_target_says_so(tmp_path: Path) -> None:
    """If the target is missing, diff exits with a clear 'no installed file' message."""
    from science_tool.project_artifacts import default_registry

    if not default_registry().artifacts:
        return
    runner = CliRunner()
    name = default_registry().artifacts[0].name
    result = runner.invoke(main, ["project", "artifacts", "diff", name, "--project-root", str(tmp_path)])
    assert result.exit_code != 0
    assert "no installed file" in result.output.lower()


def test_diff_identical_returns_empty(tmp_path: Path) -> None:
    """When installed bytes match canonical, diff exits 0 with no output."""
    from science_tool.project_artifacts import canonical_path, default_registry

    if not default_registry().artifacts:
        return
    name = default_registry().artifacts[0].name
    art = next(a for a in default_registry().artifacts if a.name == name)
    target = tmp_path / art.install_target
    target.write_bytes(canonical_path(name).read_bytes())
    runner = CliRunner()
    result = runner.invoke(main, ["project", "artifacts", "diff", name, "--project-root", str(tmp_path)])
    assert result.exit_code == 0
    assert result.output == ""
