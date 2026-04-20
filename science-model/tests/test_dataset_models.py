"""Tests for unified dataset entity Pydantic models."""

from __future__ import annotations

import pytest

from science_model.packages.schema import AccessBlock, AccessException, DerivationBlock


class TestAccessException:
    def test_default_empty(self) -> None:
        ex = AccessException()
        assert ex.mode == ""
        assert ex.decision_date == ""
        assert ex.followup_task == ""
        assert ex.superseded_by_dataset == ""
        assert ex.rationale == ""

    def test_scope_reduced(self) -> None:
        ex = AccessException(
            mode="scope-reduced", decision_date="2026-04-19", followup_task="task:t112", rationale="deferred"
        )
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
        a = AccessBlock(
            level="public",
            verified=True,
            verification_method="retrieved",
            last_reviewed="2026-04-19",
            verified_by="claude",
            source_url="https://x",
        )
        assert a.verified is True
        assert a.verification_method == "retrieved"


class TestDerivationBlock:
    def test_minimal_valid(self) -> None:
        d = DerivationBlock(
            workflow="workflow:wf",
            workflow_run="workflow-run:wf-r1",
            git_commit="abc1234",
            config_snapshot="results/wf/r1/config.yaml",
            produced_at="2026-04-19T12:00:00Z",
            inputs=["dataset:upstream"],
        )
        assert d.workflow == "workflow:wf"
        assert d.inputs == ["dataset:upstream"]

    def test_workflow_id_pattern_required(self) -> None:
        with pytest.raises(ValueError):
            DerivationBlock(
                workflow="not-a-workflow-id",
                workflow_run="workflow-run:x",
                git_commit="a",
                config_snapshot="c",
                produced_at="t",
                inputs=[],
            )

    def test_inputs_must_be_dataset_ids(self) -> None:
        with pytest.raises(ValueError):
            DerivationBlock(
                workflow="workflow:x",
                workflow_run="workflow-run:x",
                git_commit="a",
                config_snapshot="c",
                produced_at="t",
                inputs=["not-a-dataset"],
            )


from science_model.entities import EntityType


def test_research_package_entity_type_exists() -> None:
    assert EntityType("research-package") == EntityType.RESEARCH_PACKAGE


def test_data_package_entity_type_still_parses() -> None:
    """Back-compat: legacy data-package entries continue to parse as their own type."""
    assert EntityType("data-package") == EntityType.DATA_PACKAGE
