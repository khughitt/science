"""CLI tests for `entity review`."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from textwrap import dedent

from click.testing import CliRunner

from science_tool.cli import main as cli_main


def _setup_project_with_hypothesis(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    (root / "specs" / "hypotheses").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n")
    (root / "specs" / "hypotheses" / "h1.md").write_text(
        dedent(
            """
            ---
            id: "hypothesis:h1"
            kind: "hypothesis"
            title: "Demo"
            created: "2026-04-01"
            updated: "2026-04-01"
            ---
            Body.
            """
        ).lstrip()
    )
    return root


def test_entity_review_sets_last_reviewed(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    assert result.exit_code == 0, result.output

    text = (root / "specs" / "hypotheses" / "h1.md").read_text()
    today = date.today().isoformat()
    assert "review_state:" in text
    assert (
        f"last_reviewed: \"{today}\"" in text
        or f"last_reviewed: '{today}'" in text
        or f"last_reviewed: {today}" in text
    )


def test_entity_review_records_note(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(
        cli_main, ["entity", "review", "hypothesis:h1", "--note", "Re-checked after Lee2026"]
    )
    assert result.exit_code == 0, result.output

    text = (root / "specs" / "hypotheses" / "h1.md").read_text()
    assert "last_review_note" in text
    assert "Re-checked after Lee2026" in text


def test_entity_review_idempotent(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    text_first = (root / "specs" / "hypotheses" / "h1.md").read_text()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    text_second = (root / "specs" / "hypotheses" / "h1.md").read_text()
    assert text_first == text_second


def test_entity_review_unknown_id_errors(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:nonexistent"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "unknown" in result.output.lower()


def test_entity_review_preserves_existing_review_horizon_days(tmp_path: Path, monkeypatch):
    """Reviewing must not clobber other review_state fields."""
    root = _setup_project_with_hypothesis(tmp_path)
    h_path = root / "specs" / "hypotheses" / "h1.md"
    h_path.write_text(
        dedent(
            """
            ---
            id: "hypothesis:h1"
            kind: "hypothesis"
            title: "Demo"
            created: "2026-04-01"
            review_state:
              last_reviewed: "2026-04-15"
              review_horizon_days: 90
            ---
            Body.
            """
        ).lstrip()
    )
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    assert result.exit_code == 0, result.output

    text = h_path.read_text()
    assert "review_horizon_days: 90" in text
    today = date.today().isoformat()
    assert today in text


def test_entity_review_preserves_existing_note_when_no_note_passed(tmp_path: Path, monkeypatch):
    """Reviewing without --note keeps any pre-existing last_review_note."""
    root = _setup_project_with_hypothesis(tmp_path)
    h_path = root / "specs" / "hypotheses" / "h1.md"
    h_path.write_text(
        dedent(
            """
            ---
            id: "hypothesis:h1"
            kind: "hypothesis"
            title: "Demo"
            created: "2026-04-01"
            review_state:
              last_reviewed: "2026-04-15"
              last_review_note: "Original note"
            ---
            Body.
            """
        ).lstrip()
    )
    monkeypatch.chdir(root)
    runner = CliRunner()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    text = h_path.read_text()
    assert "Original note" in text


def test_entity_review_replaces_existing_note_when_new_note_passed(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    h_path = root / "specs" / "hypotheses" / "h1.md"
    h_path.write_text(
        dedent(
            """
            ---
            id: "hypothesis:h1"
            kind: "hypothesis"
            title: "Demo"
            created: "2026-04-01"
            review_state:
              last_reviewed: "2026-04-15"
              last_review_note: "Original note"
            ---
            Body.
            """
        ).lstrip()
    )
    monkeypatch.chdir(root)
    runner = CliRunner()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "New note"])
    text = h_path.read_text()
    assert "Original note" not in text
    assert "New note" in text
