"""EntityDiscoveryContext + EntityProvider abstract base.

The provider abstraction extracted from the existing 5-loader pattern in
graph/sources.py. Each provider implements discover(ctx) and returns a list
of SourceEntity. The resolver coordinates multiple providers; this module
contains only the base definitions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from science_model.ontologies.schema import OntologyCatalog

from science_tool.graph.source_types import SourceEntity


@dataclass(frozen=True)
class EntityDiscoveryContext:
    """Shared loading state passed to every EntityProvider.

    Carries everything the existing loaders depend on (local_profile, active_kinds,
    ontology_catalogs) so providers can compute profiles, validate kinds, and apply
    catalog-aware behavior without globals or per-provider re-derivation.
    """

    project_root: Path
    project_slug: str
    local_profile: str
    active_kinds: frozenset[str] | None = None
    ontology_catalogs: list["OntologyCatalog"] | None = None


class EntityProvider(ABC):
    """Discovers entities from a particular storage convention.

    Each provider is self-contained: knows where to look, knows how to read
    what it finds, returns ready-to-use SourceEntity objects with the provider
    field set. Stateless across calls (a future cache layer wraps providers).
    """

    name: str  # short human-readable identifier matching SourceEntity.provider

    @abstractmethod
    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        """Walk the filesystem under ctx.project_root and return all entities found."""
