"""Tests for StorageAdapter Protocol — persistence-only contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_model.source_ref import SourceRef
from science_tool.graph.storage_adapters.base import StorageAdapter


class _FakeAdapter(StorageAdapter):
    name = "fake"

    def discover(self, project_root: Path) -> list[SourceRef]:
        return [SourceRef(adapter_name=self.name, path="x.md")]

    def load_raw(self, ref: SourceRef) -> dict[str, object]:
        return {"id": "x:1", "canonical_id": "x:1", "kind": "concept", "title": "X"}


def test_fake_adapter_satisfies_protocol() -> None:
    a = _FakeAdapter()
    refs = a.discover(Path("/tmp"))
    assert refs[0].adapter_name == "fake"
    raw = a.load_raw(refs[0])
    assert raw["kind"] == "concept"


def test_dump_is_optional_raises_not_implemented_by_default() -> None:
    a = _FakeAdapter()
    with pytest.raises(NotImplementedError):
        a.dump(object())  # type: ignore[arg-type]


def test_base_discover_raises_not_implemented() -> None:
    """Direct instantiation of base requires subclass override."""

    class _Bare(StorageAdapter):
        name = "bare"

    b = _Bare()
    with pytest.raises(NotImplementedError):
        b.discover(Path("/tmp"))


def test_base_load_raw_raises_not_implemented() -> None:
    class _Bare(StorageAdapter):
        name = "bare"

    b = _Bare()
    with pytest.raises(NotImplementedError):
        b.load_raw(SourceRef(adapter_name="bare", path="x"))
