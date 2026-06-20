"""Unit tests for t063 overlay-model scaffolding.

Covers:
- PromoteDecision new defaulted fields (mode, existing_version).
- ExistingCanonicalConflict construction and frozen semantics.
- KEEP_EXISTING sentinel identity, repr, and distinctness.
"""

from __future__ import annotations

import dataclasses

import pytest

from science_tool.commons.promote import (
    KEEP_EXISTING,
    CanonicalArtifact,
    ExistingCanonicalConflict,
    PromoteDecision,
    _KeepExisting,
)
from science_tool.commons.promote import (
    KEEP_EXISTING as _ke2,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_decision(**overrides):
    """Build a PromoteDecision with the minimum required positional fields."""
    defaults = dict(
        slug="some-paper",
        canonical_artifacts=[],
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    defaults.update(overrides)
    return PromoteDecision(**defaults)


# ---------------------------------------------------------------------------
# PromoteDecision — new defaulted fields
# ---------------------------------------------------------------------------


class TestPromoteDecisionDefaults:
    def test_mode_defaults_to_mint(self):
        d = _minimal_decision()
        assert d.mode == "mint"

    def test_existing_version_defaults_to_none(self):
        d = _minimal_decision()
        assert d.existing_version is None

    def test_explicit_overlay_existing_round_trips(self):
        d = _minimal_decision(mode="overlay_existing", existing_version="1.0.0")
        assert d.mode == "overlay_existing"
        assert d.existing_version == "1.0.0"

    def test_existing_fields_still_positional(self):
        """The five original fields must still be accepted without keyword names."""
        artifact = CanonicalArtifact(
            path=__import__("pathlib").Path("papers/foo/entity.md"),
            content="# foo",
            validator="plain",
        )
        d = PromoteDecision(
            "my-slug",
            [artifact],
            "2.0.0",
            {},
            (),
        )
        assert d.slug == "my-slug"
        assert d.canonical_version == "2.0.0"
        assert d.mode == "mint"
        assert d.existing_version is None


# ---------------------------------------------------------------------------
# ExistingCanonicalConflict
# ---------------------------------------------------------------------------


class TestExistingCanonicalConflict:
    def test_constructs(self):
        c = ExistingCanonicalConflict(
            slug="foo-paper",
            kind="paper",
            field="title",
            source_value="New Title",
            existing_value="Old Title",
            existing_version="1.0.0",
        )
        assert c.slug == "foo-paper"
        assert c.kind == "paper"
        assert c.field == "title"
        assert c.source_value == "New Title"
        assert c.existing_value == "Old Title"
        assert c.existing_version == "1.0.0"

    def test_is_frozen(self):
        c = ExistingCanonicalConflict(
            slug="foo-paper",
            kind="paper",
            field="title",
            source_value="New Title",
            existing_value="Old Title",
            existing_version="1.0.0",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.field = "authors"  # type: ignore[misc]

    def test_all_kinds_accepted(self):
        for kind in ("paper", "topic", "theme", "dataset"):
            c = ExistingCanonicalConflict(
                slug="x",
                kind=kind,  # type: ignore[arg-type]
                field="f",
                source_value=1,
                existing_value=2,
                existing_version="0.1.0",
            )
            assert c.kind == kind

    def test_source_value_accepts_any_type(self):
        c = ExistingCanonicalConflict(
            slug="x",
            kind="dataset",
            field="tags",
            source_value=["a", "b"],
            existing_value={"key": "val"},
            existing_version="3.0.0",
        )
        assert c.source_value == ["a", "b"]
        assert c.existing_value == {"key": "val"}


# ---------------------------------------------------------------------------
# KEEP_EXISTING sentinel
# ---------------------------------------------------------------------------


class TestKeepExistingSentinel:
    def test_is_singleton(self):
        assert _ke2 is KEEP_EXISTING

    def test_repr(self):
        assert repr(KEEP_EXISTING) == "KEEP_EXISTING"

    def test_distinct_from_none(self):
        assert KEEP_EXISTING is not None
        assert KEEP_EXISTING != None  # noqa: E711

    def test_distinct_from_plain_object(self):
        assert KEEP_EXISTING is not object()

    def test_instance_of_private_class(self):
        assert isinstance(KEEP_EXISTING, _KeepExisting)

    def test_no_extra_attributes(self):
        """__slots__ = () means no per-instance __dict__."""
        assert not hasattr(KEEP_EXISTING, "__dict__")
