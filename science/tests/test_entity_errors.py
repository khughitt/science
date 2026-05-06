"""Tests for EntityIdentityCollisionError — global identity-table violations."""

from __future__ import annotations

from science_model.source_ref import SourceRef
from science_tool.graph.errors import EntityIdentityCollisionError


def test_collision_message_includes_both_sources() -> None:
    first = SourceRef(adapter_name="markdown", path="doc/datasets/x.md")
    second = SourceRef(adapter_name="datapackage", path="data/x/datapackage.yaml")
    err = EntityIdentityCollisionError("dataset:x", first, second)
    msg = str(err)
    assert "dataset:x" in msg
    assert "doc/datasets/x.md" in msg
    assert "data/x/datapackage.yaml" in msg


def test_collision_is_valueerror_subclass() -> None:
    """Consumers catching ValueError should still catch identity collisions."""
    first = SourceRef(adapter_name="a", path="p1")
    second = SourceRef(adapter_name="b", path="p2")
    err = EntityIdentityCollisionError("x:1", first, second)
    assert isinstance(err, ValueError)
