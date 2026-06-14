"""Tests for unified dataset entity Pydantic models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from science_model.entities import DatasetEntity, Entity, EntityType
from science_model.frontmatter import parse_entity_file
from science_model.packages.schema import AccessBlock, AccessException, DatasetUsage, DerivationBlock


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
        kind="dataset",
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
    assert e.access is not None
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


def test_dataset_entity_preserves_dataset_mixin_metadata() -> None:
    ds = DatasetEntity(
        **_entity_kwargs(),
        origin="external",
        access=_ext_access(),
        tier="use-now",
        update_cadence="static",
    )

    assert ds.tier == "use-now"
    assert ds.update_cadence == "static"


# Model-level invariants — fail at construction time, not only at JSON Schema check.


def test_entity_invariant_external_with_derivation_rejects() -> None:
    """origin: external ⟹ derivation must be None (#7)."""
    with pytest.raises(ValueError, match="derivation"):
        DatasetEntity(**_entity_kwargs(), origin="external", access=_ext_access(), derivation=_der_block())


def test_entity_invariant_derived_with_access_rejects() -> None:
    """origin: derived ⟹ access must be None (#8)."""
    with pytest.raises(ValueError, match="access"):
        DatasetEntity(**_entity_kwargs(), origin="derived", derivation=_der_block(), access=_ext_access())


def test_entity_invariant_derived_with_accessions_rejects() -> None:
    with pytest.raises(ValueError, match="accessions"):
        DatasetEntity(**_entity_kwargs(), origin="derived", derivation=_der_block(), accessions=["E1"])


def test_entity_invariant_derived_with_local_path_rejects() -> None:
    with pytest.raises(ValueError, match="local_path"):
        DatasetEntity(**_entity_kwargs(), origin="derived", derivation=_der_block(), local_path="data/x.csv")


def test_entity_invariant_external_missing_access_rejects() -> None:
    """A dataset entity with origin: external must carry access:."""
    with pytest.raises(ValueError, match="access"):
        DatasetEntity(**_entity_kwargs(), origin="external", access=None)


def test_entity_invariant_does_not_apply_to_non_dataset_types() -> None:
    """The origin/access/derivation invariant applies only to type=dataset."""
    e = Entity(
        id="hypothesis:h1",
        kind="hypothesis",
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


def test_external_dataset_may_carry_parent_dataset() -> None:
    """Guard: parent_dataset is origin-orthogonal.

    An origin=external (access-controlled) dataset may legally carry
    parent_dataset without a derivation block.  The invariants only constrain
    access/derivation/accessions/local_path by origin, never parent_dataset.
    This test must PASS immediately; a failure signals schema drift from the
    design claim and must be reconciled before adding sub-cohort lineage features.
    """
    ds = DatasetEntity(
        **_entity_kwargs(),
        origin="external",
        access=AccessBlock(level="controlled", verified=True),
        parent_dataset="dataset:uk-biobank",
    )
    assert ds.parent_dataset == "dataset:uk-biobank"
    assert ds.derivation is None  # parent_dataset is NOT a derivation block


def test_derived_with_produced_by_no_derivation_is_valid() -> None:
    ds = DatasetEntity(**_entity_kwargs(), origin="derived", produced_by=["code-file:stages/run.py"])
    assert ds.produced_by == ["code-file:stages/run.py"]


def test_derived_with_neither_derivation_nor_produced_by_rejects() -> None:
    with pytest.raises(ValueError, match="derivation or produced_by"):
        DatasetEntity(**_entity_kwargs(), origin="derived")


def test_external_with_produced_by_rejects() -> None:
    with pytest.raises(ValueError, match="produced_by"):
        DatasetEntity(**_entity_kwargs(), origin="external", access=_ext_access(), produced_by=["code-file:x.py"])


def test_derived_with_empty_produced_by_rejects() -> None:
    # Empty list is not a provenance path; with no derivation this must fail.
    with pytest.raises(ValueError, match="derivation or produced_by"):
        DatasetEntity(**_entity_kwargs(), origin="derived", produced_by=[])


def test_code_provenance_derived_readiness_is_ready() -> None:
    ds = DatasetEntity(**_entity_kwargs(), origin="derived", produced_by=["code-file:stages/run.py"])
    r = ds.readiness()  # no resolver needed for code provenance
    assert r.ready is True
    assert r.state == "derived-via-code"


class TestDatasetUsage:
    def test_minimal_defaults_overlap_unknown(self) -> None:
        u = DatasetUsage(ref="dataset:gtex-v8", role="analyzed")
        assert u.ref == "dataset:gtex-v8"
        assert u.role == "analyzed"
        assert u.overlap == "unknown"

    def test_training_role_full_overlap(self) -> None:
        u = DatasetUsage(ref="dataset:corpus", role="training", overlap="full")
        assert u.role == "training"
        assert u.overlap == "full"

    def test_ref_must_be_dataset_prefixed(self) -> None:
        with pytest.raises(ValueError, match="dataset:"):
            DatasetUsage(ref="paper:smith2024", role="cited")

    def test_invalid_role_rejected(self) -> None:
        with pytest.raises(ValueError):
            DatasetUsage(ref="dataset:x", role="consulted")  # type: ignore[arg-type]

    def test_invalid_overlap_rejected(self) -> None:
        with pytest.raises(ValueError):
            DatasetUsage(ref="dataset:x", role="analyzed", overlap="some")  # type: ignore[arg-type]


def test_entity_carries_source_class_and_dataset_usage() -> None:
    e = Entity(
        **_entity_kwargs(),
        origin="external",
        access=_ext_access(),
        source_class="observational",
        dataset_usage=[DatasetUsage(ref="dataset:up", role="analyzed")],
    )
    assert e.source_class == "observational"
    assert e.dataset_usage[0].role == "analyzed"


# --- enforced on the plain-Entity (parse_entity_file / plan_gate) path ---


def test_entity_dataset_kind_invalid_source_class_rejects() -> None:
    with pytest.raises(ValueError, match="source_class"):
        Entity(**_entity_kwargs(), origin="external", access=_ext_access(), source_class="curated")


def test_entity_dataset_kind_derived_requires_derived_kind() -> None:
    with pytest.raises(ValueError, match="requires derived_kind"):
        Entity(**_entity_kwargs(), origin="external", access=_ext_access(), source_class="derived")


def test_entity_dataset_kind_misplaced_derived_kind_rejects() -> None:
    with pytest.raises(ValueError, match="derived_kind is only allowed"):
        Entity(
            **_entity_kwargs(),
            origin="external",
            access=_ext_access(),
            source_class="observational",
            derived_kind="aggregate",
        )


def test_non_dataset_kind_does_not_validate_source_class() -> None:
    # Gate: the taxonomy rule applies only to kind == "dataset".
    e = Entity(
        id="hypothesis:h1",
        kind="hypothesis",
        type=EntityType.HYPOTHESIS,
        title="H1",
        project="p",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/hypotheses/h1.md",
        source_class="curated",  # not validated for non-datasets
    )
    assert e.source_class == "curated"


# --- also enforced on the graph path (DatasetEntity inherits the Entity validator) ---


def test_dataset_entity_derived_class_with_kind_ok() -> None:
    ds = DatasetEntity(
        **_entity_kwargs(),
        origin="external",
        access=_ext_access(),
        source_class="derived",
        derived_kind="model_output",
    )
    assert ds.derived_kind == "model_output"


def test_dataset_entity_invalid_source_class_rejects() -> None:
    with pytest.raises(ValueError, match="source_class"):
        DatasetEntity(
            **_entity_kwargs(), origin="external", access=_ext_access(), source_class="curated"
        )


def test_dataset_entity_invalid_source_class_rejected_without_origin() -> None:
    # The taxonomy validator is independent of origin (not behind the origin=None
    # early return in _enforce_dataset_invariants).
    with pytest.raises(ValueError, match="source_class"):
        DatasetEntity(**_entity_kwargs(), source_class="curated")


# ---------------------------------------------------------------------------
# Frontmatter parse path (Task 5)
# ---------------------------------------------------------------------------


def _write_dataset_md(tmp_path: Path, *extra_lines: str) -> Path:
    md = tmp_path / "ds.md"
    md.write_text(
        "---\n"
        "id: dataset:ds\n"
        "type: dataset\n"
        "title: A dataset\n"
        "origin: external\n"
        "tier: evaluate-next\n"
        "datapackage: data/ds/datapackage.yaml\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n" + "".join(line + "\n" for line in extra_lines) + "---\nBody.\n",
        encoding="utf-8",
    )
    return md


def test_parse_dataset_source_class_and_usage(tmp_path: Path) -> None:
    md = _write_dataset_md(
        tmp_path,
        "source_class: derived",
        "derived_kind: model_output",
        "dataset_usage:",
        "  - ref: dataset:clinvar-training",
        "    role: training",
        "    overlap: full",
    )
    e = parse_entity_file(md, project_slug="testproj")
    assert e is not None
    assert e.source_class == "derived"
    assert e.derived_kind == "model_output"
    assert len(e.dataset_usage) == 1
    assert e.dataset_usage[0].ref == "dataset:clinvar-training"
    assert e.dataset_usage[0].role == "training"
    assert e.dataset_usage[0].overlap == "full"


def test_parse_dataset_invalid_source_class_raises(tmp_path: Path) -> None:
    md = _write_dataset_md(tmp_path, "source_class: curated")
    with pytest.raises(ValidationError, match="source_class"):
        parse_entity_file(md, project_slug="testproj")


def test_parse_dataset_derived_without_kind_raises(tmp_path: Path) -> None:
    md = _write_dataset_md(tmp_path, "source_class: derived")
    with pytest.raises(ValidationError, match="derived_kind"):
        parse_entity_file(md, project_slug="testproj")


def test_parse_dataset_misplaced_derived_kind_raises(tmp_path: Path) -> None:
    md = _write_dataset_md(tmp_path, "source_class: observational", "derived_kind: aggregate")
    with pytest.raises(ValidationError, match="derived_kind"):
        parse_entity_file(md, project_slug="testproj")


def test_parse_dataset_malformed_usage_raises(tmp_path: Path) -> None:
    # A mapping authored without the leading list `-` must NOT be silently dropped.
    md = _write_dataset_md(tmp_path, "dataset_usage:", "  ref: dataset:x", "  role: training")
    with pytest.raises(ValidationError):
        parse_entity_file(md, project_slug="testproj")


def test_parse_dataset_empty_mapping_usage_raises(tmp_path: Path) -> None:
    # Present-but-non-list `dataset_usage: {}` is a defect, not "no usage" — fail early
    # (parity with the validate check), not silently coerced to [].
    md = _write_dataset_md(tmp_path, "dataset_usage: {}")
    with pytest.raises(ValidationError):
        parse_entity_file(md, project_slug="testproj")


def test_parse_dataset_usage_bad_role_raises(tmp_path: Path) -> None:
    md = _write_dataset_md(
        tmp_path, "dataset_usage:", "  - ref: dataset:x", "    role: consulted"
    )
    with pytest.raises(ValidationError):
        parse_entity_file(md, project_slug="testproj")
