"""Drives the audit/materialize unification (Slice C): single _compile pipeline."""

from __future__ import annotations

import inspect
from datetime import date
from pathlib import Path
from textwrap import dedent

from rdflib import Dataset

import science_tool.graph.materialize as m
from science_tool.graph.materialize import (
    CompilationResult,
    _build_dataset_from_sources,
    _compile,
    materialize_graph,
)
from science_tool.graph.io import REVISION_URI
from science_tool.graph.source_snapshots import compute_source_snapshots
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import DEFAULT_GRAPH_PATH, PROJECT_NS


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


# The named graphs the compiler writes. The clean fixture has no patch
# definitions, so it produces no patch named graphs — these five are complete.
_GRAPH_NAMES = ("graph/knowledge", "graph/bridge", "graph/provenance", "graph/causal", "graph/datasets")


def _quads(ds: Dataset) -> set[tuple[str, str, str, str]]:
    # Exclude graph_revision triples: save_graph_dataset adds timestamp/hash metadata
    # not present in the pure in-memory build, so filtering them lets the comparison
    # focus on semantic content.
    out: set[tuple[str, str, str, str]] = set()
    for name in _GRAPH_NAMES:
        g = ds.graph(PROJECT_NS[name])
        for s, p, o in g:
            if str(s) == str(REVISION_URI):
                continue
            out.add((str(s), str(p), str(o), name))
    return out


def _load(path: Path) -> Dataset:
    ds = Dataset()
    ds.parse(source=str(path), format="trig")
    return ds


def test_single_load_and_audit_call_sites() -> None:
    """The unification: exactly one load and one audit call site in materialize.py."""
    src = inspect.getsource(m)
    assert src.count("load_project_sources(") == 1
    assert src.count("audit_project_sources(") == 1


def test_compile_stop_after_audit_does_not_write(tmp_path: Path) -> None:
    root = _clean(tmp_path)
    result = _compile(root, stop_after="audit")

    assert isinstance(result, CompilationResult)
    assert result.dataset is None
    assert result.trig_path is None
    assert result.has_failures is False
    # audit-only writes nothing: the pre-seeded empty graph.trig is untouched.
    assert (root / DEFAULT_GRAPH_PATH).read_text() == ""


def test_materialize_write_path_matches_pure_build(tmp_path: Path) -> None:
    """The orchestrator's emit/derive/write output equals the pure build path."""
    root = _clean(tmp_path)
    sources = load_project_sources(root, strict_identity=False)
    # Compute expected FIRST, while graph.trig is still empty (same baseline the
    # materialize path will see, since the pure build writes nothing).
    snaps = compute_source_snapshots(sources, prior_graph_path=root / DEFAULT_GRAPH_PATH, today=date.today())
    expected = _quads(_build_dataset_from_sources(sources, source_snapshots=snaps))

    actual_path = materialize_graph(root, strict=False)
    actual = _quads(_load(actual_path))

    assert actual == expected
