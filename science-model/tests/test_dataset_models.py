"""Tests for unified dataset entity Pydantic models."""
from __future__ import annotations

import pytest

from science_model.packages.schema import AccessBlock, AccessException


class TestAccessException:
    def test_default_empty(self) -> None:
        ex = AccessException()
        assert ex.mode == ""
        assert ex.decision_date == ""
        assert ex.followup_task == ""
        assert ex.superseded_by_dataset == ""
        assert ex.rationale == ""

    def test_scope_reduced(self) -> None:
        ex = AccessException(mode="scope-reduced", decision_date="2026-04-19", followup_task="task:t112", rationale="deferred")
        assert ex.mode == "scope-reduced"

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValueError):
            AccessException(mode="invalid")  # type: ignore[arg-type]  # runtime validation check


class TestAccessBlock:
    def test_minimal_unverified(self) -> None:
        a = AccessBlock(level="public", verified=False)
        assert a.level == "public"
        assert a.verified is False
        assert a.verification_method == ""
        assert a.exception.mode == ""

    def test_verified_retrieved(self) -> None:
        a = AccessBlock(level="public", verified=True, verification_method="retrieved", last_reviewed="2026-04-19", verified_by="claude", source_url="https://x")
        assert a.verified is True
        assert a.verification_method == "retrieved"
