"""Tests for PromoteValidationError + plan-time validation."""

from __future__ import annotations


def test_promote_validation_error_exists_and_carries_fields() -> None:
    from science_tool.commons.errors import CommonsError, PromoteValidationError

    err = PromoteValidationError(
        decision_slug="hypothesis",
        target_kind="canonical",
        project_id=None,
        schema_message="something failed",
    )
    assert isinstance(err, CommonsError)
    assert err.decision_slug == "hypothesis"
    assert err.target_kind == "canonical"
    assert err.project_id is None
    assert "hypothesis" in str(err)
    assert "something failed" in str(err)


def test_promote_validation_error_overlay_carries_project() -> None:
    from science_tool.commons.errors import PromoteValidationError

    err = PromoteValidationError(
        decision_slug="my-theme",
        target_kind="overlay",
        project_id="proj_a",
        schema_message="overlay rejects field 'theme_kind'",
    )
    assert err.target_kind == "overlay"
    assert err.project_id == "proj_a"


def test_promote_validation_error_reexported_from_commons() -> None:
    from science_tool.commons import PromoteValidationError  # public surface

    assert PromoteValidationError is not None
