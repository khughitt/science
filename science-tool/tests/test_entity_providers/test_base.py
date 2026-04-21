"""Tests for EntityProvider ABC + EntityDiscoveryContext."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from science_tool.graph.entity_providers.base import (
    EntityDiscoveryContext,
    EntityProvider,
)
from science_tool.graph.source_types import SourceEntity


def test_entity_discovery_context_construction() -> None:
    ctx = EntityDiscoveryContext(
        project_root=Path("/tmp/x"),
        project_slug="x",
        local_profile="local",
        active_kinds=None,
        ontology_catalogs=None,
    )
    assert ctx.project_root == Path("/tmp/x")
    assert ctx.project_slug == "x"
    assert ctx.local_profile == "local"


def test_entity_discovery_context_is_frozen() -> None:
    ctx = EntityDiscoveryContext(
        project_root=Path("/tmp/x"),
        project_slug="x",
        local_profile="local",
    )
    with pytest.raises(FrozenInstanceError):
        ctx.project_slug = "y"  # type: ignore[misc]


def test_entity_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        EntityProvider()  # type: ignore[abstract]


def test_subclass_with_discover_can_instantiate() -> None:
    class FakeProvider(EntityProvider):
        name = "fake"

        def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
            return []

    p = FakeProvider()
    assert p.name == "fake"
    assert (
        p.discover(
            EntityDiscoveryContext(
                project_root=Path("/tmp/x"),
                project_slug="x",
                local_profile="local",
            )
        )
        == []
    )
