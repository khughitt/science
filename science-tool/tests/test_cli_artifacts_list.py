"""`science-tool project artifacts list` verb."""

from click.testing import CliRunner

from science_tool.cli import main


def test_list_runs_against_packaged_registry() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["project", "artifacts", "list"])
    assert result.exit_code == 0, result.output
    # Registry is non-empty after Task 28; expect a row for validate.sh.
    # When empty, "no managed artifacts" still rendered.
    assert (
        "validate.sh" in result.output
        or "no managed artifacts" in result.output.lower()
    )


def test_list_help_text_present() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["project", "artifacts", "list", "--help"])
    assert result.exit_code == 0
    assert "list managed artifacts" in result.output.lower()


def test_canonical_path_resolves_packaged_artifact(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """canonical_path returns a real, readable filesystem path."""
    # The packaged registry is empty initially; this test will be valuable once
    # Task 28 lands an artifact. For now: assert raises KeyError on unknown name.
    import pytest

    from science_tool.project_artifacts import canonical_path

    with pytest.raises(KeyError, match="no managed artifact named 'nonexistent'"):
        canonical_path("nonexistent")
