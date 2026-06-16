"""Drives the Emit/Derive phase split (Slice C)."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from rdflib import Dataset

from science_tool.graph.io import entity_uri_for_ref
from science_tool.graph.materialize import EmitResult, _emit_phase
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"), encoding="utf-8")


def _clean(root: Path) -> Path:
    demo = root / "demo"
    _write(demo / "science.yaml", "name: demo\nknowledge_profiles:\n  local: core\n")
    _write(demo / "knowledge" / "graph.trig", "")
    _write(
        demo / "entities" / "hypotheses" / "h1.md",
        """
        ---
        id: "hypothesis:h1"
        kind: "hypothesis"
        title: "Demo hypothesis"
        last_reviewed: "2026-05-01"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Original body.
        """,
    )
    return demo


def test_emit_phase_returns_build_context(tmp_path: Path) -> None:
    root = _clean(tmp_path)
    sources = load_project_sources(root, strict_identity=False)

    emit = _emit_phase(sources)

    assert isinstance(emit, EmitResult)
    assert isinstance(emit.dataset, Dataset)
    # Build context Derive needs is carried forward, not recomputed.
    assert isinstance(emit.kind_class, dict)
    assert isinstance(emit.pre_registration_targets, dict)
    # Base graph already emitted (entity present before any derive step).
    knowledge = emit.dataset.graph(PROJECT_NS["graph/knowledge"])
    assert (entity_uri_for_ref("hypothesis:h1"), None, None) in knowledge
