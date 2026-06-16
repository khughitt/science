# science/tests/test_resolve_local_home_reserved.py
"""A local kind home may not use a _-prefixed segment at any depth (P3)."""
from __future__ import annotations

import pytest

from science_tool.entities import EntityCommandError, _resolve_local_home


def test_rejects_top_level_underscore_segment() -> None:
    with pytest.raises(EntityCommandError):
        _resolve_local_home("mykind", "entities/_foo")


def test_rejects_nested_underscore_segment() -> None:
    with pytest.raises(EntityCommandError):
        _resolve_local_home("mykind", "entities/foo/_bar")


def test_rejects_archive_segment_explicitly() -> None:
    with pytest.raises(EntityCommandError):
        _resolve_local_home("mykind", "entities/_archive/mykind")


def test_accepts_normal_home() -> None:
    assert _resolve_local_home("mykind", "entities/mykind") == __import__("pathlib").Path("entities/mykind")


def test_default_home_unchanged() -> None:
    assert _resolve_local_home("mykind", None) == __import__("pathlib").Path("entities/mykind")
