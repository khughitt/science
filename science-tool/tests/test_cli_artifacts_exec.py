"""`science-tool project artifacts exec <name>` verb."""

import subprocess
import sys


def test_exec_unknown_artifact_errors() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "science_tool", "project", "artifacts", "exec", "nonexistent"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "no managed artifact named 'nonexistent'" in (proc.stdout + proc.stderr)


def test_exec_invokes_canonical_with_passed_args() -> None:
    """Once an artifact is registered (Task 28), exec should run it.

    Until then this test verifies that exec is wired and recognized."""
    proc = subprocess.run(
        [sys.executable, "-m", "science_tool", "project", "artifacts", "exec", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "exec" in proc.stdout.lower() or "name" in proc.stdout.lower()
