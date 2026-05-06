"""Tests for science_tool.dag.number — bidirectional .dot <-> edges.yaml edge-ID sync."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from science_tool.dag.number import number_all, number_one
from science_tool.dag.paths import DagPaths

FIXTURE_ROOT = Path(__file__).parent / "fixtures/mm30"
DAGS_DIR = FIXTURE_ROOT / "doc/figures/dags"


@pytest.fixture
def number_workspace(tmp_path: Path) -> Path:
    """Copy mm30 fixtures (just .dot + .edges.yaml) to writable tmp."""
    dst = tmp_path / "doc/figures/dags"
    dst.mkdir(parents=True)
    for p in DAGS_DIR.iterdir():
        if p.suffix in {".dot", ".yaml"}:
            shutil.copy2(p, dst / p.name)
    return dst


def test_number_one_is_idempotent(number_workspace: Path) -> None:
    """Running number_one twice should produce identical output both times."""
    number_one(number_workspace, "h1-progression")
    first = (number_workspace / "h1-progression-numbered.dot").read_text()
    first_yaml = (number_workspace / "h1-progression.edges.yaml").read_text()
    number_one(number_workspace, "h1-progression")
    second = (number_workspace / "h1-progression-numbered.dot").read_text()
    second_yaml = (number_workspace / "h1-progression.edges.yaml").read_text()
    assert first == second
    assert first_yaml == second_yaml


def test_number_one_preserves_existing_curation(number_workspace: Path) -> None:
    """By default, existing curation in edges.yaml must be preserved.
    force_stubs=False (default) must NOT overwrite existing data_support/descriptions.
    """
    yaml_before = yaml.safe_load((number_workspace / "h1-progression.edges.yaml").read_text())
    number_one(number_workspace, "h1-progression", force_stubs=False)
    yaml_after = yaml.safe_load((number_workspace / "h1-progression.edges.yaml").read_text())
    # Top-level content identical — this yaml was already fully curated in mm30.
    assert yaml_before == yaml_after


def test_number_all_processes_multiple_slugs(number_workspace: Path) -> None:
    paths = DagPaths(dag_dir=number_workspace, tasks_dir=number_workspace.parent, dags=None)
    number_all(paths)
    for slug in ("h1-prognosis", "h1-progression", "h2-subtype-architecture", "h1-h2-bridge"):
        assert (number_workspace / f"{slug}-numbered.dot").exists(), f"{slug}-numbered.dot missing"


def test_number_one_force_stubs_resets_curation(number_workspace: Path) -> None:
    """force_stubs=True wipes data_support / lit_support / description on every edge.
    This is destructive and documented in mm30's README as an intentional curation reset.
    """
    yaml_before = yaml.safe_load((number_workspace / "h1-progression.edges.yaml").read_text())
    assert yaml_before["edges"][0].get("description", "").strip(), "fixture precondition: description is set"

    number_one(number_workspace, "h1-progression", force_stubs=True)
    yaml_after = yaml.safe_load((number_workspace / "h1-progression.edges.yaml").read_text())
    # After force_stubs, the data_support/description should be reset (mm30 script
    # replaces them with empty placeholders).
    first = yaml_after["edges"][0]
    # Depending on the mm30 reset behavior (stubs or empty), verify destruction:
    assert not first.get("description", "").strip() or "TODO" in first["description"], (
        "force_stubs should have reset the description"
    )


def test_numbered_dot_has_edge_labels(number_workspace: Path) -> None:
    """The -numbered.dot output must contain [N] prefixes on every edge."""
    number_one(number_workspace, "h1-progression")
    text = (number_workspace / "h1-progression-numbered.dot").read_text()
    # h1-progression has 6 edges, so [1] through [6] must appear.
    for n in range(1, 7):
        assert f"[{n}]" in text, f"Edge label [{n}] missing from numbered dot"
