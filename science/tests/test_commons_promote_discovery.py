"""Tests for science_tool.commons.promote — discovery + module surface."""

from __future__ import annotations

import pytest


def test_promote_module_imports() -> None:
    from science_tool.commons import promote  # noqa: F401


def test_dataclass_surface_is_frozen() -> None:
    from science_tool.commons.promote import (
        ConflictResolution,
        DiscoveryResult,
        FailedCandidate,
        FieldConflict,
        OverlayRewrite,
        PromoteCandidate,
        PromoteDecision,
        PromotePlan,
        PromoteResult,
    )

    for cls in (
        PromoteCandidate,
        FieldConflict,
        ConflictResolution,
        OverlayRewrite,
        PromoteDecision,
        FailedCandidate,
        DiscoveryResult,
        PromotePlan,
        PromoteResult,
    ):
        # frozen=True is the authoritative flag on the dataclass params
        assert cls.__dataclass_params__.frozen, f"{cls.__name__} must be frozen"
