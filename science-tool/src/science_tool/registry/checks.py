"""Proactive registry checks for entity deduplication."""

from __future__ import annotations

from science_tool.registry.index import RegistryIndex, load_registry_index
from science_tool.registry.matching import MatchResult, find_matches

_cached_index: RegistryIndex | None = None


def check_registry(
    canonical_id: str,
    *,
    aliases: list[str],
    ontology_terms: list[str],
    candidate_kind: str | None = None,
    candidate_title: str | None = None,
    registry_index: RegistryIndex | None = None,
) -> list[MatchResult]:
    """Check if an entity matches anything in the registry.

    Read-only, advisory. After registry namespacing, Tier 1 (exact canonical ID)
    matching is effectively disabled for cross-project lookups since registry entities
    use namespaced IDs (project::local_id). Matching still works via Tier 2 (aliases)
    and Tier 3 (ontology terms).
    """
    if registry_index is None:
        registry_index = _get_cached_index()

    return find_matches(
        canonical_id,
        aliases=aliases,
        ontology_terms=ontology_terms,
        registry_entities=registry_index.entities,
        candidate_kind=candidate_kind,
        candidate_title=candidate_title,
    )


def _get_cached_index() -> RegistryIndex:
    global _cached_index
    if _cached_index is None:
        _cached_index = load_registry_index()
    return _cached_index


def clear_cache() -> None:
    """Clear the cached registry index (for testing)."""
    global _cached_index
    _cached_index = None
