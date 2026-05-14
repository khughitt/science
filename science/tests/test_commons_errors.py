"""Tests for science_tool.commons.errors."""
from __future__ import annotations

from pathlib import Path

from science_tool.commons.errors import (
    CommonsDatapackageError,
    CommonsEntityError,
    CommonsError,
    CommonsLayoutError,
    CommonsRegistryError,
    CommonsRootMalformedError,
    CommonsRootNotFoundError,
    DataIntegrityError,
    DataLogicalPathError,
    DataResourceNotFoundError,
    OverlayMergeError,
    OverlayValidationError,
    ProjectDirectoryMissingError,
    ProjectNotRegisteredError,
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


def test_phase_c_errors_subclass_commons_error() -> None:
    assert issubclass(CommonsDatapackageError, CommonsError)
    assert issubclass(DataLogicalPathError, CommonsError)
    assert issubclass(DataResourceNotFoundError, CommonsError)
    assert issubclass(DataIntegrityError, CommonsError)


def test_datapackage_error_carries_path_and_reason() -> None:
    err = CommonsDatapackageError(Path("/x/datapackage.yaml"), reason="missing resources[]")
    assert err.path == Path("/x/datapackage.yaml")
    assert err.reason == "missing resources[]"
    assert "missing resources[]" in str(err)
    assert "/x/datapackage.yaml" in str(err)


def test_logical_path_error_carries_string_not_path() -> None:
    err = DataLogicalPathError("../escape", reason="path may not contain '..' segments")
    assert err.logical_path == "../escape"
    assert err.reason == "path may not contain '..' segments"
    assert "../escape" in str(err)


def test_resource_not_found_lists_tried_paths() -> None:
    tried = [Path("/data/foo/x.tsv"), Path("/legacy/foo/x.tsv")]
    err = DataResourceNotFoundError("dataset:foo", "x.tsv", tried=tried)
    assert err.dataset_id == "dataset:foo"
    assert err.logical_path == "x.tsv"
    assert err.tried == tried
    assert "/data/foo/x.tsv" in str(err)
    assert "/legacy/foo/x.tsv" in str(err)


def test_integrity_error_carries_expected_and_actual() -> None:
    err = DataIntegrityError(
        Path("/data/foo/x.tsv"),
        expected="sha256:aaaa",
        actual="sha256:bbbb",
    )
    assert err.path == Path("/data/foo/x.tsv")
    assert err.expected == "sha256:aaaa"
    assert err.actual == "sha256:bbbb"
    assert "sha256:aaaa" in str(err)
    assert "sha256:bbbb" in str(err)


def test_project_not_registered_error_carries_name() -> None:
    exc = ProjectNotRegisteredError("protein-landscape")
    assert isinstance(exc, CommonsError)
    assert exc.name == "protein-landscape"
    assert "protein-landscape" in str(exc)


def test_project_directory_missing_error_carries_project_and_path() -> None:
    exc = ProjectDirectoryMissingError("protein-landscape", Path("/gone/pl"))
    assert isinstance(exc, CommonsError)
    assert exc.project == "protein-landscape"
    assert exc.path == Path("/gone/pl")
    assert "/gone/pl" in str(exc)


def test_overlay_validation_error_carries_cause() -> None:
    cause = ValueError("schema boom")
    exc = OverlayValidationError(
        Path("/p/doc/papers/Adams2025.md"),
        canonical_id="paper:Adams2025",
        cause=cause,
    )
    assert isinstance(exc, CommonsError)
    assert exc.overlay_path == Path("/p/doc/papers/Adams2025.md")
    assert exc.canonical_id == "paper:Adams2025"
    assert exc.cause is cause
    assert "schema boom" in str(exc)
    assert "Adams2025.md" in str(exc)


def test_overlay_merge_error_carries_field_and_id() -> None:
    exc = OverlayMergeError(field="title", canonical_id="paper:Adams2025")
    assert isinstance(exc, CommonsError)
    assert exc.field == "title"
    assert exc.canonical_id == "paper:Adams2025"
    assert "title" in str(exc)
