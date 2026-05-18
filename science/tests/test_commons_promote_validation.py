"""Tests for PromoteValidationError + plan-time validation."""

from __future__ import annotations

import pytest


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


def test_plan_promote_validates_canonical_against_kind_profile(tmp_path, monkeypatch) -> None:
    """A canonical that violates its mixin schema fails plan_promote with
    PromoteValidationError (no I/O). Build a paper candidate with a year
    out of the permitted range (paper mixin requires 1800-2200)."""
    from science_tool.commons.errors import PromoteValidationError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        discover_candidates,
        plan_promote,
    )

    proj = tmp_path / "proj_v"
    (proj / "doc" / "papers").mkdir(parents=True)
    (proj / "doc" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntitle: A\nyear: 99\n---\n",
        encoding="utf-8",
    )
    commons = tmp_path / "commons"
    commons.mkdir()

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj_v"], PROMOTE_KIND_PAPER)
    with pytest.raises(PromoteValidationError) as excinfo:
        plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_PAPER)
    err = excinfo.value
    assert err.decision_slug == "Adams2025"
    assert err.target_kind == "canonical"
    assert err.project_id is None
    assert "year" in err.schema_message.lower() or "99" in err.schema_message


def test_plan_promote_wraps_overlay_validation_failure(tmp_path, monkeypatch) -> None:
    from science_model.entity_schema import EntityValidationError, EntityValidator
    from science_tool.commons.errors import PromoteValidationError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        discover_candidates,
        plan_promote,
    )

    proj = tmp_path / "proj_overlay"
    (proj / "doc" / "papers").mkdir(parents=True)
    (proj / "doc" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntitle: A\nyear: 2025\ntags: [local]\n---\n",
        encoding="utf-8",
    )
    commons = tmp_path / "commons"
    commons.mkdir()

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    def fail_overlay(self: EntityValidator, overlay: dict) -> None:
        assert overlay["overlay_of"] == "paper:Adams2025"
        raise EntityValidationError("overlay rejected for test")

    monkeypatch.setattr(EntityValidator, "validate_overlay", fail_overlay)

    discovery = discover_candidates(["proj_overlay"], PROMOTE_KIND_PAPER)
    with pytest.raises(PromoteValidationError) as excinfo:
        plan_promote(discovery, commons_root=commons, kind=PROMOTE_KIND_PAPER)

    err = excinfo.value
    assert err.decision_slug == "Adams2025"
    assert err.target_kind == "overlay"
    assert err.project_id == "proj_overlay"
    assert "overlay rejected for test" in err.schema_message


def test_plan_validation_dispatches_by_artifact_validator(tmp_path, monkeypatch):
    """An artifact with validator='plain' is skipped; 'entity-mixin' runs EntityValidator()."""
    from pathlib import Path

    from science_tool.commons.promote import (
        CanonicalArtifact,
        _validate_artifact,
    )

    plain = CanonicalArtifact(
        path=Path("datasets/x/recipe/README.md"),
        content="# Recipe back-fill needed\n",
        validator="plain",
    )
    # Should NOT raise:
    _validate_artifact(plain, decision_slug="x", project_id=None)

    # Minimal mixin artifact: still missing required dataset-mixin fields
    # (origin/tier/access), so the science_model EntityValidator will reject it.
    mixin = CanonicalArtifact(
        path=Path("datasets/x/entity.md"),
        content=(
            "---\n"
            "schema_profile: science-entity-base/1.0+dataset/1.0\n"
            "id: dataset:x\n"
            "type: dataset\n"
            "title: x\n"
            "version: 1.0.0\n"
            "created: '2026-05-18'\n"
            "updated: '2026-05-18'\n"
            "---\n"
        ),
        validator="entity-mixin",
    )
    import pytest

    from science_tool.commons.errors import PromoteValidationError

    with pytest.raises(PromoteValidationError):
        _validate_artifact(mixin, decision_slug="x", project_id=None)
