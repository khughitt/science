"""CLI tests for `entity review`."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from textwrap import dedent

from click.testing import CliRunner

from science_tool.cli import main as cli_main
from science_tool.graph.materialize import materialize_graph


def _setup_project_with_hypothesis(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    (root / "entities" / "hypotheses").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n")
    (root / "entities" / "hypotheses" / "h1.md").write_text(
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

    text = (root / "entities" / "hypotheses" / "h1.md").read_text()
    today = date.today().isoformat()
    assert "review_state:" in text
    assert (
        f'last_reviewed: "{today}"' in text or f"last_reviewed: '{today}'" in text or f"last_reviewed: {today}" in text
    )


def test_entity_review_records_note(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "Re-checked after Lee2026"])
    assert result.exit_code == 0, result.output

    text = (root / "entities" / "hypotheses" / "h1.md").read_text()
    assert "last_review_note" in text
    assert "Re-checked after Lee2026" in text


def test_entity_review_idempotent(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    text_first = (root / "entities" / "hypotheses" / "h1.md").read_text()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    text_second = (root / "entities" / "hypotheses" / "h1.md").read_text()
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
    h_path = root / "entities" / "hypotheses" / "h1.md"
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
    h_path = root / "entities" / "hypotheses" / "h1.md"
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
    h_path = root / "entities" / "hypotheses" / "h1.md"
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


def test_entity_review_clears_existing_note_when_empty_string_passed(tmp_path: Path, monkeypatch):
    """Passing --note '' clears any pre-existing last_review_note."""
    root = _setup_project_with_hypothesis(tmp_path)
    h_path = root / "entities" / "hypotheses" / "h1.md"
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
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", ""])
    text = h_path.read_text()
    assert "last_review_note" not in text
    assert "Original note" not in text


def _setup_with_built_graph(tmp_path: Path) -> Path:
    """Project where graph build has run and h1 ends up needs-review.

    Uses a `task` fixture (not workflow-run) because materialize.py converts
    `related: [hypothesis:foo]` to `sci:tests` only when the source kind is
    `task` — see materialize.py:220 and T9's integration test fixture.
    """
    root = _setup_project_with_hypothesis(tmp_path)
    (root / "doc" / "tasks").mkdir(parents=True)
    (root / "doc" / "tasks" / "t1.md").write_text(
        dedent(
            """
            ---
            id: "task:t1"
            kind: "task"
            title: "Demo task"
            status: "active"
            created: "2026-05-01"
            updated: "2026-05-01"
            related: ["hypothesis:h1"]
            ---
            Body.
            """
        ).lstrip()
    )
    materialize_graph(root)
    return root


def test_entity_needs_review_lists_flagged(tmp_path: Path, monkeypatch):
    root = _setup_with_built_graph(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "needs-review"])
    assert result.exit_code == 0, result.output
    assert "hypothesis:h1" in result.output
    assert "needs-review" in result.output


def test_entity_needs_review_json_format(tmp_path: Path, monkeypatch):
    root = _setup_with_built_graph(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "needs-review", "--format", "json"])
    assert result.exit_code == 0, result.output

    payload = json.loads(result.output)
    assert payload["format"] == "json"
    rows = payload["rows"]
    ids = {row["id"] for row in rows}
    assert "hypothesis:h1" in ids


def test_entity_needs_review_empty_when_all_fresh(tmp_path: Path, monkeypatch):
    """If h1's last_reviewed is set after the upstream change, it shouldn't be flagged."""
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    materialize_graph(root)
    result = runner.invoke(cli_main, ["entity", "needs-review"])
    assert result.exit_code == 0, result.output
    assert "hypothesis:h1" not in result.output


def _setup_project_with_dataset(tmp_path: Path) -> Path:
    """Project with a dataset entity placed under the hypotheses root so find_entity can load it.

    _load_markdown_entities scans policy-rooted directories (entities/) and includes any
    entity whose frontmatter has a valid id/kind — so a file with kind:dataset
    placed in entities/hypotheses/ is discoverable by find_entity("dataset:d1").

    Scope: this exercises the registry-gate logic in review_entity(). It does
    not prove the gate fires when a dataset is discovered via its canonical
    path; in real projects datasets aren't loaded through find_entity at all
    (no entry in _BUILTIN_MARKDOWN_POLICIES — they flow through dedicated
    adapters like DatapackageAdapter).
    """
    root = tmp_path / "demo"
    (root / "entities" / "hypotheses").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n")
    (root / "entities" / "hypotheses" / "d1.md").write_text(
        dedent(
            """
            ---
            id: "dataset:d1"
            kind: "dataset"
            title: "Demo dataset"
            created: "2026-04-01"
            updated: "2026-04-01"
            ---
            Body.
            """
        ).lstrip()
    )
    return root


def test_entity_review_rejects_non_epistemic_target(tmp_path: Path, monkeypatch):
    root = _setup_project_with_dataset(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "dataset:d1"])
    assert result.exit_code != 0, result.output
    assert "non-epistemic" in result.output.lower() or "operational" in result.output.lower()
