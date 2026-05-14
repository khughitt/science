"""Tests for science_tool.commons.errors."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsError,
    CommonsLayoutError,
    CommonsRegistryError,
    CommonsRootMalformedError,
    CommonsRootNotFoundError,
)


def test_all_errors_subclass_commons_error() -> None:
    assert issubclass(CommonsRootNotFoundError, CommonsError)
    assert issubclass(CommonsRootMalformedError, CommonsError)
    assert issubclass(CommonsLayoutError, CommonsError)
    assert issubclass(CommonsEntityError, CommonsError)
    assert issubclass(CommonsRegistryError, CommonsError)


def test_root_not_found_carries_path() -> None:
    err = CommonsRootNotFoundError(Path("/nope"))
    assert err.root == Path("/nope")
    assert "/nope" in str(err)


def test_root_malformed_lists_missing() -> None:
    err = CommonsRootMalformedError(Path("/x"), missing=["datasets", ".git"])
    assert err.root == Path("/x")
    assert err.missing == ["datasets", ".git"]
    assert "datasets" in str(err)
    assert ".git" in str(err)


def test_layout_error_carries_path_and_reason() -> None:
    err = CommonsLayoutError(Path("/x/datasets/foo"), reason="missing datapackage.yaml sibling")
    assert err.path == Path("/x/datasets/foo")
    assert "missing datapackage.yaml sibling" in str(err)


def test_entity_error_wraps_cause() -> None:
    inner = ValueError("bad yaml")
    err = CommonsEntityError(Path("/x/papers/bad.md"), canonical_id="paper:bad", cause=inner)
    assert err.path == Path("/x/papers/bad.md")
    assert err.canonical_id == "paper:bad"
    assert err.cause is inner
    assert "bad.md" in str(err)


def test_entity_error_allows_unknown_canonical_id() -> None:
    err = CommonsEntityError(Path("/x/papers/bad.md"), canonical_id=None, cause=RuntimeError("x"))
    assert err.canonical_id is None


def test_registry_error_carries_db_path() -> None:
    inner = RuntimeError("locked")
    err = CommonsRegistryError(Path("/x/registry.sqlite"), cause=inner)
    assert err.db_path == Path("/x/registry.sqlite")
    assert err.cause is inner
