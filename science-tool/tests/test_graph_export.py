"""Tests for shared graph export payload types."""

from pathlib import Path

import pytest

from science_tool.graph.export_types import GraphExportOverlays, GraphExportPayload
from science_tool.graph.store import INITIAL_GRAPH_TEMPLATE


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for export tests."""
    graph_file = tmp_path / "knowledge" / "graph.trig"
    graph_file.parent.mkdir(parents=True)
    graph_file.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return graph_file


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
