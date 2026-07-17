"""CLI tests for `entity review`."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner
from _fixtures.entity_helpers import write_markdown_entity

from science_tool.cli import main as cli_main
from science_tool.entity_review import ReviewError, review_entity
from science_tool.graph.materialize import materialize_graph


@pytest.fixture
def review_project(tmp_project: Path) -> Path:
    write_markdown_entity(
        tmp_project,
        "entities/plans/0001.md",
        {"id": "plan:0001", "kind": "plan", "title": "Implementation plan", "status": "active"},
    )
    write_markdown_entity(
        tmp_project,
        "entities/datasets/example.md",
        {"id": "dataset:example", "kind": "dataset", "title": "Example dataset", "status": "active"},
    )
    return tmp_project


@pytest.fixture
def review_project_with_design(tmp_project_with_design_kind: Path) -> Path:
    write_markdown_entity(
        tmp_project_with_design_kind,
        "entities/design/0001.md",
        {"id": "design:0001", "kind": "design", "title": "Local design", "status": "active"},
    )
    return tmp_project_with_design_kind


def test_review_admits_plan(review_project: Path) -> None:
    """Design acceptance test 4: a correspondence kind is reviewable."""
    path, changed = review_entity(
        review_project,
        "plan:0001",
        note="shipped: ships in commit abc",
        require_artifact=True,
    )

    assert changed
    assert "last_reviewed" in path.read_text()


def test_review_refuses_dataset(review_project: Path) -> None:
    """Design acceptance test 5: a none-scoped kind is refused at the boundary."""
    with pytest.raises(ReviewError, match="curation_scope 'none'"):
        review_entity(review_project, "dataset:example", note="x", require_artifact=True)


def test_review_theater_guard_on_plan(review_project: Path) -> None:
    """A bare timestamp bump on a plan is refused without an artifact."""
    with pytest.raises(ReviewError, match="recorded artifact"):
        review_entity(review_project, "plan:0001", note=None, require_artifact=True)


def test_review_admits_local_extension_kind(review_project_with_design: Path) -> None:
    """An undeclared local extension scope defaults to reviewable correspondence."""
    path, changed = review_entity(
        review_project_with_design,
        "design:0001",
        note="matches the shipped module layout",
        require_artifact=True,
    )

    assert changed
    assert "last_reviewed" in path.read_text()


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
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "checked"])
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
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "checked"])
    text_first = (root / "entities" / "hypotheses" / "h1.md").read_text()
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "checked"])
    text_second = (root / "entities" / "hypotheses" / "h1.md").read_text()
    assert text_first == text_second


def test_entity_review_unknown_id_errors(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:nonexistent"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "unknown" in result.output.lower()


def test_entity_review_malformed_policy_yaml_is_clean_cli_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _setup_project_with_hypothesis(tmp_path)
    (root / "science.yaml").write_text("knowledge_profiles: [\n", encoding="utf-8")
    monkeypatch.chdir(root)

    result = CliRunner().invoke(
        cli_main,
        ["entity", "review", "hypothesis:h1", "--note", "checked"],
    )

    assert result.exit_code == 1
    assert "Error: Entity policy configuration is not valid:" in result.output
    assert "Traceback" not in result.output


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
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "horizon check"])
    assert result.exit_code == 0, result.output

    text = h_path.read_text()
    assert "review_horizon_days: 90" in text
    today = date.today().isoformat()
    assert today in text


def test_review_entity_preserves_existing_note_when_note_is_none(tmp_path: Path):
    """review_entity(note=None) keeps any pre-existing last_review_note."""
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
    review_entity(root, "hypothesis:h1", note=None)
    assert "Original note" in h_path.read_text()


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


def test_review_entity_clears_note_on_empty_string(tmp_path: Path):
    """review_entity(note="") clears any pre-existing last_review_note."""
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
    review_entity(root, "hypothesis:h1", note="")
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
    (root / "entities" / "tasks").mkdir(parents=True)
    (root / "entities" / "tasks" / "t1.md").write_text(
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
    runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "reviewed for freshness"])
    materialize_graph(root)
    result = runner.invoke(cli_main, ["entity", "needs-review"])
    assert result.exit_code == 0, result.output
    assert "hypothesis:h1" not in result.output


def _setup_project_with_dataset(tmp_path: Path) -> Path:
    """Project with a dataset entity under its canonical markdown root."""
    root = tmp_path / "demo"
    (root / "entities" / "datasets").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n")
    (root / "entities" / "datasets" / "d1.md").write_text(
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


def test_entity_review_rejects_none_scoped_target(tmp_path: Path, monkeypatch):
    root = _setup_project_with_dataset(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "dataset:d1"])
    assert result.exit_code != 0, result.output
    assert "curation_scope 'none'" in result.output


def test_entity_review_requires_artifact(tmp_path: Path, monkeypatch):
    """A bare `entity review` (no --note) is review-theater and must be refused."""
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1"])
    assert result.exit_code != 0
    assert "artifact" in result.output.lower() or "note" in result.output.lower()
    # frontmatter must be untouched
    text = (root / "entities" / "hypotheses" / "h1.md").read_text()
    assert "review_state:" not in text


def test_entity_review_rejects_blank_note(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:h1", "--note", "   "])
    assert result.exit_code != 0
    assert "artifact" in result.output.lower() or "note" in result.output.lower()


def test_entity_review_succeeds_with_artifact(tmp_path: Path, monkeypatch):
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        ["entity", "review", "hypothesis:h1", "--note", "scope re-checked vs constants.py::EVENTS; no change"],
    )
    assert result.exit_code == 0, result.output
    text = (root / "entities" / "hypotheses" / "h1.md").read_text()
    assert "scope re-checked" in text


def test_entity_review_unknown_id_errors_even_without_note(tmp_path: Path, monkeypatch):
    """Unknown id with no --note must still report 'not found', not 'needs artifact'."""
    root = _setup_project_with_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["entity", "review", "hypothesis:nonexistent"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "unknown" in result.output.lower()
    assert "artifact" not in result.output.lower()
