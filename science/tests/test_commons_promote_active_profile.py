"""Tests for `_active_profile` -- builds the runtime ProfileString from
PromoteKindConfig + mixin extensions tuple.
"""
from __future__ import annotations

from science_model.entity_schema.profile import ProfileComponent
from science_tool.commons.promote import (
    PROMOTE_KIND_DATASET,
    PROMOTE_KIND_PAPER,
    _active_profile,
)


def test_no_extensions_returns_kind_default() -> None:
    profile = _active_profile(PROMOTE_KIND_PAPER, ())
    assert profile.base.name == "science-entity-base"
    assert profile.mixin is not None
    assert profile.mixin.name == "paper"
    assert profile.extensions == ()


def test_dataset_with_matrix_and_rnaseq() -> None:
    extensions = (
        ProfileComponent(name="bio.matrix", version="1.0"),
        ProfileComponent(name="bio.rnaseq", version="1.0"),
    )
    profile = _active_profile(PROMOTE_KIND_DATASET, extensions)
    assert profile.mixin is not None
    assert profile.mixin.name == "dataset"
    assert profile.extensions == extensions
    rendered = profile.render()
    assert rendered.endswith("+bio.matrix/1.0+bio.rnaseq/1.0")
    assert rendered.startswith("science-entity-base/1.0+dataset/1.0")


def test_returned_profile_is_a_new_object() -> None:
    """Doesn't mutate the PromoteKindConfig's frozen default_profile."""
    extensions = (ProfileComponent(name="bio.matrix", version="1.0"),)
    profile = _active_profile(PROMOTE_KIND_DATASET, extensions)
    assert PROMOTE_KIND_DATASET.default_profile.extensions == ()
    assert profile.extensions == extensions
