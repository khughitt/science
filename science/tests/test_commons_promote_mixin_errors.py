"""Unit tests for the new mixin-related promote error classes."""
from __future__ import annotations

from science_tool.commons.errors import (
    CommonsError,
    PromoteInputError,
    PromoteMixinResolutionError,
    PromoteMixinStackingError,
)


def test_stacking_error_is_promote_input_error() -> None:
    err = PromoteMixinStackingError("two structural mixins not allowed")
    assert isinstance(err, PromoteInputError)
    assert isinstance(err, CommonsError)
    assert "two structural" in str(err)


def test_resolution_error_is_promote_input_error() -> None:
    err = PromoteMixinResolutionError("no installed bio.bogus")
    assert isinstance(err, PromoteInputError)
    assert isinstance(err, CommonsError)
    assert "no installed" in str(err)
