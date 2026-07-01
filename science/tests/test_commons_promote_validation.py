"""Tests for PromoteValidationError + plan-time validation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _init_commons_repo(root: Path) -> Path:
    """Init `root` as an empty git repo so plan_promote's existing-canonical
    lookup (git tag --list) has a repo to query. No tags → mint path."""
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@x"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "test"], check=True)
    return root


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
    (proj / "entities" / "papers").mkdir(parents=True)
    (proj / "entities" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntitle: A\nyear: 99\n---\n",
        encoding="utf-8",
    )
    commons = _init_commons_repo(tmp_path / "commons")

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


def test_skip_on_invalid_drops_bad_decision_and_keeps_valid(tmp_path, monkeypatch) -> None:
    """One schema-invalid candidate must not abort a whole batch promote.

    With skip_on_invalid=True (set for non-interactive runs), a candidate whose
    canonical fails plan-time validation is dropped into a PromoteValidationSkipped
    soft-failure and the valid candidates still promote — instead of aborting the
    entire run on the first bad entity (fb-2026-05-31-002).
    """
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        discover_candidates,
        plan_promote,
    )

    proj = tmp_path / "proj_mixed"
    (proj / "entities" / "papers").mkdir(parents=True)
    (proj / "entities" / "papers" / "Good2025.md").write_text(
        "---\nid: paper:Good2025\ntitle: Good\nyear: 2025\n---\n",
        encoding="utf-8",
    )
    (proj / "entities" / "papers" / "Bad2025.md").write_text(
        "---\nid: paper:Bad2025\ntitle: Bad\nyear: 99\n---\n",
        encoding="utf-8",
    )
    commons = _init_commons_repo(tmp_path / "commons")

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    discovery = discover_candidates(["proj_mixed"], PROMOTE_KIND_PAPER)
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_PAPER,
        skip_on_invalid=True,
    )

    promoted = {d.slug for d in plan.decisions}
    assert "Good2025" in promoted
    assert "Bad2025" not in promoted
    skipped = [
        fc for fc in plan.failed_candidates if fc.error_class == "PromoteValidationSkipped"
    ]
    assert len(skipped) == 1
    assert skipped[0].slug == "Bad2025"
    assert "year" in skipped[0].error_message.lower() or "99" in skipped[0].error_message


def test_plan_promote_wraps_overlay_validation_failure(tmp_path, monkeypatch) -> None:
    from science_model.entity_schema import EntityValidationError, EntityValidator

    from science_tool.commons.errors import PromoteValidationError
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        discover_candidates,
        plan_promote,
    )

    proj = tmp_path / "proj_overlay"
    (proj / "entities" / "papers").mkdir(parents=True)
    (proj / "entities" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntitle: A\nyear: 2025\ntags: [local]\n---\n",
        encoding="utf-8",
    )
    commons = _init_commons_repo(tmp_path / "commons")

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


def test_entity_validator_accepts_access_reproducibility_block() -> None:
    """access.reproducibility is a Pydantic-only enum gate; the JSON mixin schema
    stays permissive (no additionalProperties: false on access), so a dataset
    entity carrying the block must pass EntityValidator unchanged."""
    from science_model.entity_schema import EntityValidator

    entity = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0",
        "id": "dataset:enclave-cohort",
        "type": "dataset",
        "title": "Enclave cohort",
        "version": "1.0.0",
        "created": "2026-06-30",
        "updated": "2026-06-30",
        "origin": "external",
        "tier": "evaluate-next",
        "datapackage": "datapackage.yaml",
        "access": {
            "level": "controlled",
            "verified": True,
            "reproducibility": {
                "obtainability": "approved-project",
                "execution": "trusted-environment",
                "extractability": "aggregate-reviewed",
                "notes": "Only reviewed aggregates leave the enclave.",
            },
        },
    }

    validator = EntityValidator()
    assert list(validator.validate(entity) or []) == []


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

    with pytest.raises(PromoteValidationError) as excinfo:
        _validate_artifact(mixin, decision_slug="x", project_id=None)
    err = excinfo.value
    assert err.decision_slug == "x"
    assert err.target_kind == "canonical"
    assert err.project_id is None
    assert err.schema_message
    assert str(err)


def test_plan_validation_wraps_missing_datapackage_parser(tmp_path, monkeypatch):
    from pathlib import Path

    from science_tool.commons import datapackage
    from science_tool.commons.errors import PromoteValidationError
    from science_tool.commons.promote import (
        CanonicalArtifact,
        _validate_artifact,
    )

    artifact = CanonicalArtifact(
        path=Path("datasets/x/datapackage.yaml"),
        content="resources: []\n",
        validator="frictionless-datapackage",
    )

    monkeypatch.delattr(datapackage, "parse_canonical_datapackage_yaml", raising=False)

    with pytest.raises(PromoteValidationError) as excinfo:
        _validate_artifact(artifact, decision_slug="x", project_id="proj")

    err = excinfo.value
    assert err.decision_slug == "x"
    assert err.target_kind == "canonical"
    assert err.project_id == "proj"
    assert "parse_canonical_datapackage_yaml" in err.schema_message


def test_plan_validation_does_not_wrap_datapackage_module_import_failure(monkeypatch):
    from pathlib import Path

    import science_tool.commons.promote as promote
    from science_tool.commons.promote import (
        CanonicalArtifact,
        _validate_artifact,
    )

    artifact = CanonicalArtifact(
        path=Path("datasets/x/datapackage.yaml"),
        content="resources: []\n",
        validator="frictionless-datapackage",
    )

    def fail_datapackage_import(name: str):
        if name == "science_tool.commons.datapackage":
            raise ImportError("datapackage dependency exploded")
        raise AssertionError(f"unexpected import: {name}")

    monkeypatch.setattr(promote, "import_module", fail_datapackage_import)

    with pytest.raises(ImportError, match="datapackage dependency exploded"):
        _validate_artifact(artifact, decision_slug="x", project_id="proj")
