"""CLI: science annotate lift-tokens (mirror + remove modes)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.annotation.io import read_sidecar

FX = Path(__file__).parent / "_fixtures" / "annotation" / "audit"


@pytest.fixture
def git_workspace(tmp_path: Path) -> Path:
    doc = tmp_path / "doc"
    doc.mkdir()
    shutil.copy(FX / "mixed-tokens.md", doc / "mixed-tokens.md")
    shutil.copy(FX / "clean-after-remove.md", doc / "clean-after-remove.md")
    shutil.copy(FX / "paper.v1.md", doc / "paper.v1.md")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t",
         "add", "."],
        cwd=tmp_path, check=True,
    )
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t",
         "commit", "-qm", "init"],
        cwd=tmp_path, check=True,
    )
    return tmp_path


def test_mirror_writes_sidecar_prose_unchanged(git_workspace: Path) -> None:
    runner = CliRunner()
    md = git_workspace / "doc" / "clean-after-remove.md"
    before = md.read_text()
    result = runner.invoke(
        annotate_group,
        ["lift-tokens", "--root", str(git_workspace), "--actor", "tester"],
    )
    assert result.exit_code == 0
    sidecar = git_workspace / "doc" / "clean-after-remove.anno.trig"
    assert sidecar.exists()
    assert md.read_text() == before


def test_remove_strips_tokens_and_writes_sidecar(git_workspace: Path) -> None:
    runner = CliRunner()
    expected_text = (FX / "clean-after-remove.expected.md").read_text()
    md = git_workspace / "doc" / "clean-after-remove.md"
    sidecar = md.with_suffix(".anno.trig")
    result = runner.invoke(
        annotate_group,
        [
            "lift-tokens", "--root", str(git_workspace),
            "--remove", "--actor", "tester",
        ],
    )
    assert result.exit_code == 0, result.output
    assert md.read_text() == expected_text
    sc = read_sidecar(sidecar)
    # Selectors should anchor to cleaned prose (no [UNVERIFIED] etc.).
    for ann in sc.annotations:
        assert "[UNVERIFIED]" not in ann.target.selector.exact
        assert "[MISSING_CITATION]" not in ann.target.selector.exact
        assert ann.lifted_from is not None


def test_remove_refuses_dirty_tree(git_workspace: Path) -> None:
    runner = CliRunner()
    md = git_workspace / "doc" / "clean-after-remove.md"
    md.write_text(md.read_text() + "\n\nExtra dirty line.\n")
    result = runner.invoke(
        annotate_group,
        [
            "lift-tokens", "--root", str(git_workspace),
            "--remove", "--actor", "tester",
        ],
    )
    assert result.exit_code == 1
    assert "dirty" in (result.output + (result.stderr or "")).lower()


def test_remove_force_dirty_overrides(git_workspace: Path) -> None:
    runner = CliRunner()
    md = git_workspace / "doc" / "clean-after-remove.md"
    md.write_text(md.read_text() + "\n\nExtra dirty line.\n")
    result = runner.invoke(
        annotate_group,
        [
            "lift-tokens", "--root", str(git_workspace),
            "--remove", "--force-dirty", "--actor", "tester",
        ],
    )
    assert result.exit_code == 0


def test_idempotent_mirror_rerun(git_workspace: Path) -> None:
    runner = CliRunner()
    args = ["lift-tokens", "--root", str(git_workspace), "--actor", "t"]
    runner.invoke(annotate_group, args)
    sidecar = git_workspace / "doc" / "clean-after-remove.anno.trig"
    before = sidecar.read_text()
    result = runner.invoke(annotate_group, args)
    assert result.exit_code == 0
    assert sidecar.read_text() == before


def test_multi_dotted_name_sidecar_path(git_workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        ["lift-tokens", "--root", str(git_workspace), "--actor", "t"],
    )
    assert result.exit_code == 0
    assert (git_workspace / "doc" / "paper.v1.anno.trig").exists()
    # The double-with_suffix bug would have created paper.anno.trig.
    assert not (git_workspace / "doc" / "paper.anno.trig").exists()


def test_recoverable_replay_after_simulated_partial_failure(
    git_workspace: Path,
) -> None:
    """If sidecar wrote OK but prose write was 'lost' (we simulate by
    restoring the .md), a re-run still produces correct steady-state."""
    runner = CliRunner()
    md = git_workspace / "doc" / "clean-after-remove.md"
    sidecar = md.with_suffix(".anno.trig")
    expected_text = (FX / "clean-after-remove.expected.md").read_text()
    original_text = md.read_text()
    # First run: writes sidecar (cleaned-prose selectors) AND prose.
    runner.invoke(annotate_group, [
        "lift-tokens", "--root", str(git_workspace),
        "--remove", "--actor", "t",
    ])
    assert sidecar.exists()
    # Simulate partial failure: restore prose to original (tokens back).
    md.write_text(original_text)
    # Re-run: dedupe skips existing rows; prose strip succeeds.
    result = runner.invoke(annotate_group, [
        "lift-tokens", "--root", str(git_workspace),
        "--remove", "--force-dirty", "--actor", "t",
    ])
    assert result.exit_code == 0
    assert md.read_text() == expected_text


def test_format_json_summary_shape(git_workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "lift-tokens", "--root", str(git_workspace),
        "--format", "json", "--actor", "tester",
    ])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "summary" in payload
    assert payload["summary"]["files_scanned"] >= 1
    assert "rows_written" in payload["summary"]
