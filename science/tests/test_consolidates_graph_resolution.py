"""Graph build: digest sci:consolidates -> archived member tombstone (P4)."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.consolidate import apply_consolidation, scaffold_digest
from science_tool.entities import create_entity

rdflib = pytest.importorskip("rdflib")


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def test_digest_consolidates_edge_targets_tombstone(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_entity(root, "finding", "A", entity_id="finding:0001-a")
    scaffold_digest(root, digest_id="synthesis:0001-d", member_ids=["finding:0001-a"], title="D")
    apply_consolidation(root, "synthesis:0001-d", apply=True, now="T1")

    from science_tool.graph.materialize import materialize_graph

    out_path = materialize_graph(root, strict=False)
    text = out_path.read_text(encoding="utf-8")

    assert "consolidates" in text          # the sci:consolidates edge (predicate) is emitted
    assert "0001-a" in text                # the archived member id appears as the edge target
    assert "ArchivedEntity" in text        # the member is a typed tombstone stub, not rehydrated
    # the archived member markdown is NOT pulled back into the live tree
    assert not (root / "entities" / "findings" / "0001-a.md").exists()
