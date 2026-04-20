"""Tests for unified dataset entity Pydantic models."""

from __future__ import annotations

import pytest

from science_model.entities import Entity, EntityType
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


def test_research_package_entity_type_exists() -> None:
    assert EntityType("research-package") == EntityType.RESEARCH_PACKAGE


def test_data_package_entity_type_still_parses() -> None:
    """Back-compat: legacy data-package entries continue to parse as their own type."""
    assert EntityType("data-package") == EntityType.DATA_PACKAGE


def _entity_kwargs() -> dict:
    return dict(
        id="dataset:x",
        type=EntityType.DATASET,
        title="X",
        project="testproj",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/datasets/x.md",
    )


def _ext_access() -> AccessBlock:
    return AccessBlock(
        level="public",
        verified=True,
        verification_method="retrieved",
        last_reviewed="2026-04-19",
        source_url="https://x",
    )


def _der_block() -> DerivationBlock:
    return DerivationBlock(
        workflow="workflow:wf",
        workflow_run="workflow-run:wf-r1",
        git_commit="abc",
        config_snapshot="c",
        produced_at="2026-04-19T12:00:00Z",
        inputs=["dataset:up"],
    )


def test_entity_external_origin_with_access_block() -> None:
    e = Entity(
        **_entity_kwargs(),
        origin="external",
        access=_ext_access(),
        accessions=["EGAD0001"],
        datapackage="data/x/datapackage.yaml",
        local_path="",
        consumed_by=["plan:p1"],
        parent_dataset="",
        siblings=[],
    )
    assert e.origin == "external"
    assert e.access.verified is True
    assert e.derivation is None


def test_entity_derived_origin_with_derivation_block() -> None:
    e = Entity(
        **_entity_kwargs(),
        origin="derived",
        derivation=_der_block(),
        datapackage="results/wf/r1/x/datapackage.yaml",
        consumed_by=[],
        parent_dataset="",
        siblings=[],
    )
    assert e.origin == "derived"
    assert e.derivation is not None
    assert e.access is None


# Model-level invariants — fail at construction time, not only at JSON Schema check.


def test_entity_invariant_external_with_derivation_rejects() -> None:
    """origin: external ⟹ derivation must be None (#7)."""
    import pytest

    with pytest.raises(ValueError, match="derivation"):
        Entity(**_entity_kwargs(), origin="external", access=_ext_access(), derivation=_der_block())


def test_entity_invariant_derived_with_access_rejects() -> None:
    """origin: derived ⟹ access must be None (#8)."""
    import pytest

    with pytest.raises(ValueError, match="access"):
        Entity(**_entity_kwargs(), origin="derived", derivation=_der_block(), access=_ext_access())


def test_entity_invariant_derived_with_accessions_rejects() -> None:
    import pytest

    with pytest.raises(ValueError, match="accessions"):
        Entity(**_entity_kwargs(), origin="derived", derivation=_der_block(), accessions=["E1"])


def test_entity_invariant_derived_with_local_path_rejects() -> None:
    import pytest

    with pytest.raises(ValueError, match="local_path"):
        Entity(**_entity_kwargs(), origin="derived", derivation=_der_block(), local_path="data/x.csv")


def test_entity_invariant_external_missing_access_rejects() -> None:
    """A dataset entity with origin: external must carry access:."""
    import pytest

    with pytest.raises(ValueError, match="access"):
        Entity(**_entity_kwargs(), origin="external", access=None)


def test_entity_invariant_derived_missing_derivation_rejects() -> None:
    import pytest

    with pytest.raises(ValueError, match="derivation"):
        Entity(**_entity_kwargs(), origin="derived", derivation=None)


def test_entity_invariant_does_not_apply_to_non_dataset_types() -> None:
    """The origin/access/derivation invariant applies only to type=dataset."""
    e = Entity(
        id="hypothesis:h1",
        type=EntityType.HYPOTHESIS,
        title="H1",
        project="p",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/hypotheses/h1.md",
    )
    assert e.origin is None  # no constraint
