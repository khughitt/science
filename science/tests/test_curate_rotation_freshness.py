"""graph_source precedence tests for adaptive rotation enrichment."""

from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

from science_tool.curate.rotation import graph_freshness
from science_tool.graph.materialize import materialize_graph


def _project_with_hypothesis_and_task(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    (root / "entities" / "hypotheses").mkdir(parents=True)
    (root / "entities" / "tasks").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n", encoding="utf-8")
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
        ).lstrip(),
        encoding="utf-8",
    )
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
        ).lstrip(),
        encoding="utf-8",
    )
    return root


def test_graph_source_absent(tmp_path: Path) -> None:
    root = _project_with_hypothesis_and_task(tmp_path)  # no materialize
    source, states = graph_freshness(root)
    assert source == "absent"
    assert states == {}


def test_graph_source_invalid(tmp_path: Path) -> None:
    root = _project_with_hypothesis_and_task(tmp_path)
    graph_path = root / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text("this is not valid trig {{{", encoding="utf-8")
    source, states = graph_freshness(root)
    assert source == "invalid"
    assert states == {}


def test_graph_source_stale(tmp_path: Path) -> None:
    root = _project_with_hypothesis_and_task(tmp_path)
    materialize_graph(root)
    graph_path = root / "knowledge" / "graph.trig"
    os.utime(graph_path, (1000, 1000))  # force the graph older than every source
    source, states = graph_freshness(root)
    assert source == "stale"
    assert states == {}


def test_graph_source_current_yields_states(tmp_path: Path) -> None:
    root = _project_with_hypothesis_and_task(tmp_path)
    materialize_graph(root)
    graph_path = root / "knowledge" / "graph.trig"
    os.utime(graph_path, (2_000_000_000, 2_000_000_000))  # force the graph newer than every source
    source, states = graph_freshness(root)
    assert source == "current"
    assert states.get("hypothesis:h1") == "needs-review"


def test_graph_source_invalid_on_staleness_failure(tmp_path: Path, monkeypatch) -> None:
    """A parseable graph whose staleness check raises degrades to invalid, not a crash."""
    root = _project_with_hypothesis_and_task(tmp_path)
    materialize_graph(root)

    def _boom(*_args: object, **_kwargs: object) -> bool:
        raise OSError("simulated read failure")

    # Patch the name as bound inside the rotation module (best-effort must catch this).
    monkeypatch.setattr("science_tool.curate.rotation.graph_is_stale", _boom)
    source, states = graph_freshness(root)
    assert source == "invalid"
    assert states == {}


def test_graph_source_invalid_on_probe_failure(tmp_path: Path, monkeypatch) -> None:
    """Even the existence probe is best-effort: if Path.exists raises, degrade to invalid."""
    root = _project_with_hypothesis_and_task(tmp_path)  # no materialize; probe raises before parse

    def _boom(_self: Path) -> bool:
        raise OSError("simulated stat failure")

    monkeypatch.setattr(Path, "exists", _boom)
    source, states = graph_freshness(root)
    assert source == "invalid"
    assert states == {}
