"""Tests for science_tool.dag.number."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from science_tool.dag.number import number_all, number_one
from science_tool.dag.paths import DagPaths

FIXTURE_ROOT = Path(__file__).parent / "fixtures/mm30"
DAGS_DIR = FIXTURE_ROOT / "doc/figures/dags"


@pytest.fixture
def number_workspace(tmp_path: Path) -> Path:
    """Copy mm30 DOT fixtures to writable tmp."""
    dst = tmp_path / "doc/figures/dags"
    dst.mkdir(parents=True)
    for p in DAGS_DIR.iterdir():
        if p.suffix == ".dot":
            shutil.copy2(p, dst / p.name)
    return dst


def test_number_one_does_not_create_edges_yaml_for_new_dot(tmp_path: Path) -> None:
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "new.dot").write_text("digraph new {\n  a -> b;\n}\n", encoding="utf-8")

    number_one(dag_dir, "new", proposition_edges=[])

    assert (dag_dir / "new-numbered.dot").exists()
    assert not (dag_dir / "new.edges.yaml").exists()


def test_number_one_force_stubs_is_retired(number_workspace: Path) -> None:
    with pytest.raises(ValueError, match="retired"):
        number_one(number_workspace, "h1-progression", force_stubs=True, proposition_edges=[])


def test_number_one_is_idempotent(number_workspace: Path) -> None:
    """Running number_one twice should produce identical output both times."""
    number_one(number_workspace, "h1-progression")
    first = (number_workspace / "h1-progression-numbered.dot").read_text()
    assert not (number_workspace / "h1-progression.edges.yaml").exists()

    number_one(number_workspace, "h1-progression")
    second = (number_workspace / "h1-progression-numbered.dot").read_text()

    assert first == second


def test_number_all_processes_multiple_slugs(number_workspace: Path) -> None:
    paths = DagPaths(dag_dir=number_workspace, tasks_dir=number_workspace.parent, dags=None)
    number_all(paths)
    for slug in ("h1-prognosis", "h1-progression", "h2-subtype-architecture", "h1-h2-bridge"):
        assert (number_workspace / f"{slug}-numbered.dot").exists(), f"{slug}-numbered.dot missing"
        assert not (number_workspace / f"{slug}.edges.yaml").exists(), f"{slug}.edges.yaml was created"


def test_numbered_dot_has_edge_labels(number_workspace: Path) -> None:
    """The -numbered.dot output must contain [N] prefixes on every edge."""
    number_one(number_workspace, "h1-progression")
    text = (number_workspace / "h1-progression-numbered.dot").read_text()
    assert not (number_workspace / "h1-progression.edges.yaml").exists()
    # h1-progression has 6 edges, so [1] through [6] must appear.
    for n in range(1, 7):
        assert f"[{n}]" in text, f"Edge label [{n}] missing from numbered dot"
