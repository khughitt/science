"""Tests for shared graph export payload types."""

from pathlib import Path

import pytest

from science_tool.graph.export_types import GraphExportOverlays, GraphExportPayload
from science_tool.graph.store import INITIAL_GRAPH_TEMPLATE


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for testing."""
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return gp


def test_graph_export_fixture_creates_fresh_graph(graph_path: Path) -> None:
    assert graph_path.read_text(encoding="utf-8") == INITIAL_GRAPH_TEMPLATE


def test_export_types_roundtrip_minimal_payload() -> None:
    payload = GraphExportPayload(
        schema_version="1",
        nodes=[],
        edges=[],
        layers=[],
        scopes=[],
        overlays=GraphExportOverlays(),
        warnings=[],
    )

    assert payload.model_dump()["schema_version"] == "1"
