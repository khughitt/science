"""Tests for _validate_artifact's handling of unknown bio extensions."""
from __future__ import annotations

import pytest

from science_tool.commons.errors import PromoteMixinResolutionError
from science_tool.commons.promote import CanonicalArtifact, _validate_artifact


def test_validate_artifact_wraps_schema_not_found_as_resolution_error() -> None:
    """When canonical content cites an unknown bio.* extension, the
    SchemaNotFoundError raised by EntityValidator._compose is caught and
    re-raised as PromoteMixinResolutionError for consistent CLI UX."""
    content = (
        "---\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0+bio.bogus/1.0\n"
        "id: dataset:x\n"
        "kind: dataset\n"
        "title: x\n"
        "version: 1.0.0\n"
        "created: '2026-05-19'\n"
        "updated: '2026-05-19'\n"
        "datapackage: datapackage.yaml\n"
        "origin: external\n"
        "tier: use-now\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n"
        "---\n"
        "Body.\n"
    )
    artifact = CanonicalArtifact(
        path="datasets/x/entity.md",
        content=content,
        validator="entity-mixin",
    )
    with pytest.raises(PromoteMixinResolutionError, match="bio.bogus"):
        _validate_artifact(artifact, decision_slug="x", project_id=None)
