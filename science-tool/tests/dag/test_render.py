from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from science_tool.dag.paths import DagPaths
from science_tool.dag.render import render_all, render_one

FIXTURE_ROOT = Path(__file__).parent / "fixtures/mm30"
DAGS_DIR = FIXTURE_ROOT / "doc/figures/dags"
SLUGS = ("h1-prognosis", "h1-progression", "h2-subtype-architecture", "h1-h2-bridge")


@pytest.fixture
def render_workspace(tmp_path: Path) -> Path:
    """Copy mm30 fixtures to a writable tmp location; return the dag_dir."""
    dst = tmp_path / "doc/figures/dags"
    dst.mkdir(parents=True)
    # Copy .dot + .edges.yaml + .dot.reference (for test comparison)
    for p in DAGS_DIR.iterdir():
        if p.suffix in {".dot", ".yaml"} or p.name.endswith(".dot.reference"):
            shutil.copy2(p, dst / p.name)
    return dst


def test_render_all_byte_identical_dot_vs_mm30_reference(render_workspace: Path) -> None:
    paths = DagPaths(dag_dir=render_workspace, tasks_dir=render_workspace.parent, dags=None)
    render_all(paths)
    for slug in SLUGS:
        produced = (render_workspace / f"{slug}-auto.dot").read_text()
        expected = (render_workspace / f"{slug}-auto.dot.reference").read_text()
        assert produced == expected, f"{slug}: .dot drifted from mm30 reference"


def test_render_one_handles_eliminated_edge(render_workspace: Path) -> None:
    # h1-h2-bridge fixture has 2 eliminated edges (state->rib, state->e2f).
    render_one(render_workspace, "h1-h2-bridge")
    dot = (render_workspace / "h1-h2-bridge-auto.dot").read_text()
    # Both eliminated edges must carry the #9e9e9e color and [✗] marker.
    assert dot.count("#9e9e9e") >= 2, "expected at least 2 eliminated-grey edges"
    assert dot.count("[✗]") >= 2, "expected at least 2 [✗] eliminated markers"


def test_render_one_structural_invariants(render_workspace: Path) -> None:
    render_one(render_workspace, "h1-progression")
    yaml_path = render_workspace / "h1-progression.edges.yaml"
    dot = (render_workspace / "h1-progression-auto.dot").read_text()
    edges = yaml.safe_load(yaml_path.read_text())["edges"]
    for edge in edges:
        assert f"[{edge['id']}]" in dot, f"edge id [{edge['id']}] missing from rendered .dot"


def test_render_discovers_slugs_when_whitelist_absent(render_workspace: Path) -> None:
    paths = DagPaths(dag_dir=render_workspace, tasks_dir=render_workspace.parent, dags=None)
    render_all(paths)
    for slug in SLUGS:
        assert (render_workspace / f"{slug}-auto.dot").exists()


def test_render_png_failure_is_non_fatal(render_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If graphviz `dot` is absent/fails, render_all should log-and-continue."""
    import subprocess

    def _fail(*a: object, **kw: object) -> None:
        raise FileNotFoundError("simulated missing graphviz")

    monkeypatch.setattr(subprocess, "run", _fail)
    paths = DagPaths(dag_dir=render_workspace, tasks_dir=render_workspace.parent, dags=None)
    render_all(paths)  # must NOT raise
    # .dot was still written:
    for slug in SLUGS:
        assert (render_workspace / f"{slug}-auto.dot").exists()
