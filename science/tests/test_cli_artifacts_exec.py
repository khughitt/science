"""`science project artifacts exec <name>` verb."""

from click.testing import CliRunner

from science_tool.cli import main


def test_exec_unknown_artifact_errors() -> None:
    result = CliRunner().invoke(main, ["project", "artifacts", "exec", "nonexistent"])
    assert result.exit_code != 0
    assert "no managed artifact named 'nonexistent'" in result.output


def test_exec_invokes_canonical_with_passed_args() -> None:
    """Once an artifact is registered (Task 28), exec should run it.

    Until then this test verifies that exec is wired and recognized."""
    result = CliRunner().invoke(main, ["project", "artifacts", "exec", "--help"])
    assert result.exit_code == 0
    assert "exec" in result.output.lower() or "name" in result.output.lower()
