"""CLI tests for `graph propagate-freshness` — read-only sweep."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from click.testing import CliRunner

from science_tool.cli import main as cli_main


def _build_project_with_stale_hypothesis(tmp_path: Path) -> Path:
    """Project where h1 should be flagged as needs-review.

    Uses a `task` fixture (not workflow-run) because materialize.py converts
    `related: [hypothesis:foo]` to sci:tests only when the source kind is
    `task`. The hypothesis lives under `specs/hypotheses/` per the project's
    _BUILTIN_MARKDOWN_POLICIES.
    """
    root = tmp_path / "demo"
    (root / "specs" / "hypotheses").mkdir(parents=True)
    (root / "doc" / "tasks").mkdir(parents=True)
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
    return root


def test_propagate_freshness_reports_needs_review(tmp_path: Path, monkeypatch):
    root = _build_project_with_stale_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    runner = CliRunner()
    result = runner.invoke(cli_main, ["graph", "propagate-freshness"])
    assert result.exit_code == 0, result.output
    assert "hypothesis:h1" in result.output
    assert "needs-review" in result.output


def test_propagate_freshness_does_not_write_graph(tmp_path: Path, monkeypatch):
    """Sweep must be read-only — the graph file is not created if absent."""
    root = _build_project_with_stale_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    trig = root / "knowledge" / "graph.trig"
    runner = CliRunner()
    runner.invoke(cli_main, ["graph", "propagate-freshness"])
    assert not trig.exists()


def test_propagate_freshness_does_not_mutate_entity_files(tmp_path: Path, monkeypatch):
    root = _build_project_with_stale_hypothesis(tmp_path)
    monkeypatch.chdir(root)
    h_path = root / "specs" / "hypotheses" / "h1.md"
    before_mtime = h_path.stat().st_mtime_ns

    runner = CliRunner()
    runner.invoke(cli_main, ["graph", "propagate-freshness"])

    assert h_path.stat().st_mtime_ns == before_mtime


def _build_project_with_unresolved_ref(tmp_path: Path) -> Path:
    """Project where the hypothesis cites a non-existent paper."""
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
            source_refs: ["paper:does-not-exist"]
            ---
            Body.
            """
        ).lstrip()
    )
    return root


def test_propagate_freshness_raises_on_unresolved_refs(tmp_path: Path) -> None:
    import pytest
    from science_tool.graph.freshness import propagate_freshness_in_memory

    project_root = _build_project_with_unresolved_ref(tmp_path)
    with pytest.raises(ValueError, match="unresolved references"):
        propagate_freshness_in_memory(project_root)
