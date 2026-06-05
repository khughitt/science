"""freshness.enabled: false opt-out for downstream projects mid-migration."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from rdflib import Dataset

from science_tool.graph.freshness import propagate_freshness_in_memory
from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"))


def _build_minimal_project(tmp_path: Path, *, freshness_enabled: bool | None) -> Path:
    """One epistemic entity + one task that tests it. freshness_enabled=None omits the block."""
    root = tmp_path / "demo"
    yaml = "name: demo\nknowledge_profiles:\n  local: core\n"
    if freshness_enabled is not None:
        yaml += f"freshness:\n  enabled: {'true' if freshness_enabled else 'false'}\n"
    _write(root / "science.yaml", yaml)
    _write(
        root / "entities" / "hypotheses" / "h1.md",
        """
        ---
        id: "hypothesis:h1"
        kind: "hypothesis"
        title: "Demo"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Body.
    """,
    )
    _write(
        root / "entities" / "tasks" / "t1.md",
        """
        ---
        id: "task:t1"
        kind: "task"
        title: "Demo"
        status: "active"
        created: "2026-05-01"
        updated: "2026-05-01"
        related: ["hypothesis:h1"]
        ---
        Body.
    """,
    )
    return root


def _knowledge(trig_path: Path):
    ds = Dataset()
    ds.parse(trig_path, format="trig")
    return ds.graph(PROJECT_NS["graph/knowledge"])


def test_freshness_disabled_skips_state_emission(tmp_path: Path) -> None:
    project_root = _build_minimal_project(tmp_path, freshness_enabled=False)
    trig_path = materialize_graph(project_root)
    knowledge = _knowledge(trig_path)
    # No freshness state triples.
    assert list(knowledge.triples((None, SCI_NS.freshnessState, None))) == []
    # bears_on still emitted (independent of freshness).
    bears = list(knowledge.triples((None, SCI_NS.bearsOn, None)))
    assert len(bears) > 0


def test_propagate_freshness_returns_empty_when_disabled(tmp_path: Path) -> None:
    project_root = _build_minimal_project(tmp_path, freshness_enabled=False)
    assert propagate_freshness_in_memory(project_root) == []


def test_freshness_enabled_default_emits_state(tmp_path: Path) -> None:
    project_root = _build_minimal_project(tmp_path, freshness_enabled=None)
    trig_path = materialize_graph(project_root)
    knowledge = _knowledge(trig_path)
    states = list(knowledge.triples((None, SCI_NS.freshnessState, None)))
    assert len(states) > 0


def test_freshness_explicitly_enabled_emits_state(tmp_path: Path) -> None:
    project_root = _build_minimal_project(tmp_path, freshness_enabled=True)
    trig_path = materialize_graph(project_root)
    knowledge = _knowledge(trig_path)
    states = list(knowledge.triples((None, SCI_NS.freshnessState, None)))
    assert len(states) > 0
