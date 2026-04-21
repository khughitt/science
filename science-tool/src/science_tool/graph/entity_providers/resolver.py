"""EntityResolver — coordinates a list of EntityProvider implementations.

Runs all providers, concatenates their outputs, raises EntityIdCollisionError
on duplicate canonical_ids. The collision error names BOTH provider sources so
debugging is direct.
"""

from __future__ import annotations

from science_tool.graph.entity_providers.base import EntityDiscoveryContext, EntityProvider
from science_tool.graph.source_types import EntityIdCollisionError, SourceEntity


class EntityResolver:
    """Runs a list of providers and merges their outputs."""

    def __init__(self, providers: list[EntityProvider]) -> None:
        self._providers = providers

    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        seen: dict[str, list[tuple[str, str]]] = {}
        all_entities: list[SourceEntity] = []
        for provider in self._providers:
            for entity in provider.discover(ctx):
                seen.setdefault(entity.canonical_id, []).append((provider.name, entity.source_path))
                all_entities.append(entity)
        collisions = {cid: srcs for cid, srcs in seen.items() if len(srcs) > 1}
        if collisions:
            cid, sources = next(iter(collisions.items()))
            raise EntityIdCollisionError(cid, sources)
        return all_entities


def default_providers() -> list[EntityProvider]:
    """The set of providers active in every project. No config required.

    Function (not constant) so tests can construct ad-hoc providers without
    monkey-patching, and so the import order doesn't force eager construction.
    """
    from science_tool.graph.entity_providers.markdown import MarkdownProvider
    from science_tool.graph.entity_providers.datapackage_directory import DatapackageDirectoryProvider
    from science_tool.graph.entity_providers.aggregate import AggregateProvider

    return [
        MarkdownProvider(),
        DatapackageDirectoryProvider(),
        AggregateProvider(),
    ]
