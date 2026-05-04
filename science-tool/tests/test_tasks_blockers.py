"""Tests for blocker ref validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from _fixtures.entity_helpers import seed_project, write_markdown_entity
from science_model.entities import DatasetEntity
from science_tool.entities import load_local_entity_ids, load_local_entity_index
from science_tool.tasks_blockers import (
    BlockerValidationError,
    validate_blocker_refs,
)


def _setup_project_with_dataset(tmp_path: Path) -> Path:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/datasets/foo.md",
        {
            "id": "dataset:foo",
            "type": "dataset",
            "title": "Foo",
            "status": "active",
            "origin": "external",
            "access": {"level": "public", "verified": True},
        },
    )
    return tmp_path


def test_load_local_entity_ids_returns_project_entity_ids(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    ids = load_local_entity_ids(tmp_path)
    assert "dataset:foo" in ids


def test_load_local_entity_index_returns_project_entities(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    index = load_local_entity_index(tmp_path)
    assert isinstance(index["dataset:foo"], DatasetEntity)


def test_validate_rejects_untyped_string(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    with pytest.raises(BlockerValidationError, match="must be typed"):
        validate_blocker_refs(tmp_path, ["just-a-string"])


def test_validate_rejects_untyped_even_with_force(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    with pytest.raises(BlockerValidationError, match="must be typed"):
        validate_blocker_refs(tmp_path, ["just-a-string"], force=True)


def test_validate_accepts_known_typed_ref(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    result = validate_blocker_refs(tmp_path, ["dataset:foo"])
    assert result == ["dataset:foo"]


def test_validate_rejects_unknown_typed_ref(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    with pytest.raises(BlockerValidationError, match="unknown entity"):
        validate_blocker_refs(tmp_path, ["dataset:does-not-exist"])


def test_validate_force_accepts_unknown_typed_ref(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    result = validate_blocker_refs(tmp_path, ["dataset:does-not-exist"], force=True)
    assert result == ["dataset:does-not-exist"]


def test_validate_multiple_refs_reports_first_failure(tmp_path: Path):
    _setup_project_with_dataset(tmp_path)
    with pytest.raises(BlockerValidationError, match="dataset:bogus"):
        validate_blocker_refs(tmp_path, ["dataset:foo", "dataset:bogus"])
