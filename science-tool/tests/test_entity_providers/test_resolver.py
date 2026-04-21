"""Tests for EntityResolver — coordinates multiple providers, merges by canonical_id."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.entity_providers.base import EntityDiscoveryContext, EntityProvider
from science_tool.graph.entity_providers.resolver import EntityResolver, default_providers
from science_tool.graph.source_types import EntityIdCollisionError, SourceEntity


def _ctx() -> EntityDiscoveryContext:
    return EntityDiscoveryContext(
        project_root=Path("/tmp/x"),
        project_slug="x",
        local_profile="local",
    )


def _entity(canonical_id: str, source_path: str) -> SourceEntity:
    return SourceEntity(
        canonical_id=canonical_id,
        kind="hypothesis",
        title=canonical_id,
        profile="local",
        source_path=source_path,
        provider="markdown",
    )


class _StaticProvider(EntityProvider):
    """Test double — returns a fixed list."""

    def __init__(self, name: str, entities: list[SourceEntity]) -> None:
        self.name = name
        self._entities = entities

    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        return self._entities


def test_empty_provider_list_yields_empty_result() -> None:
    resolver = EntityResolver([])
    assert resolver.discover(_ctx()) == []


def test_single_provider_passes_through() -> None:
    p = _StaticProvider("a", [_entity("hypothesis:h1", "doc/hypotheses/h1.md")])
    resolver = EntityResolver([p])
    out = resolver.discover(_ctx())
    assert len(out) == 1
    assert out[0].canonical_id == "hypothesis:h1"


def test_multiple_providers_concatenated() -> None:
    p1 = _StaticProvider("a", [_entity("hypothesis:h1", "h1.md")])
    p2 = _StaticProvider("b", [_entity("dataset:d1", "d1.md")])
    resolver = EntityResolver([p1, p2])
    out = resolver.discover(_ctx())
    ids = {e.canonical_id for e in out}
    assert ids == {"hypothesis:h1", "dataset:d1"}


def test_collision_across_providers_raises() -> None:
    p1 = _StaticProvider("a", [_entity("hypothesis:h1", "via-a.md")])
    p2 = _StaticProvider("b", [_entity("hypothesis:h1", "via-b.md")])
    resolver = EntityResolver([p1, p2])
    with pytest.raises(EntityIdCollisionError) as exc_info:
        resolver.discover(_ctx())
    msg = str(exc_info.value)
    assert "hypothesis:h1" in msg
    assert "a: via-a.md" in msg
    assert "b: via-b.md" in msg


def test_collision_within_one_provider_raises() -> None:
    p = _StaticProvider(
        "a",
        [
            _entity("hypothesis:h1", "h1.md"),
            _entity("hypothesis:h1", "h1-dup.md"),
        ],
    )
    resolver = EntityResolver([p])
    with pytest.raises(EntityIdCollisionError):
        resolver.discover(_ctx())


def test_default_providers_returns_three_v1_implementations() -> None:
    providers = default_providers()
    names = [p.name for p in providers]
    assert names == ["markdown", "datapackage-directory", "aggregate"]
