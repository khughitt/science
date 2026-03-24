"""Tiered entity matching for cross-project registry lookups."""

from __future__ import annotations

from enum import IntEnum

from pydantic import BaseModel

from science_tool.registry.index import RegistryEntity


class MatchTier(IntEnum):
    """Match confidence tiers, ordered from highest to lowest."""

    EXACT = 1
    ALIAS = 2
    ONTOLOGY = 3
    FUZZY = 4


class MatchResult(BaseModel):
    """A match between a candidate entity and a registry entry."""

    entity: RegistryEntity
    tier: MatchTier


def find_matches(
    canonical_id: str,
    *,
    aliases: list[str],
    ontology_terms: list[str],
    registry_entities: list[RegistryEntity],
    candidate_kind: str | None = None,
    candidate_title: str | None = None,
) -> list[MatchResult]:
    """Find registry entities matching a candidate, returning highest-tier match only.

    Tiers 1-3 are auto-resolvable. Tier 4 (fuzzy) is for user review.
    """
    best: MatchResult | None = None

    candidate_aliases = {a.lower() for a in aliases}
    candidate_aliases.add(canonical_id.lower())
    candidate_ontology = set(ontology_terms)

    for entry in registry_entities:
        tier = _match_tier(
            entry,
            canonical_id=canonical_id,
            candidate_aliases=candidate_aliases,
            candidate_ontology=candidate_ontology,
            candidate_kind=candidate_kind,
            candidate_title=candidate_title,
        )
        if tier is None:
            continue
        if best is None or tier < best.tier:
            best = MatchResult(entity=entry, tier=tier)

    return [best] if best is not None else []


def _match_tier(
    entry: RegistryEntity,
    *,
    canonical_id: str,
    candidate_aliases: set[str],
    candidate_ontology: set[str],
    candidate_kind: str | None,
    candidate_title: str | None,
) -> MatchTier | None:
    # Tier 1: exact canonical ID
    if entry.canonical_id == canonical_id:
        return MatchTier.EXACT

    # Tier 2: alias overlap
    entry_aliases = {a.lower() for a in entry.aliases}
    entry_aliases.add(entry.canonical_id.lower())
    if candidate_aliases & entry_aliases:
        return MatchTier.ALIAS

    # Tier 3: ontology term overlap
    if candidate_ontology and candidate_ontology & set(entry.ontology_terms):
        return MatchTier.ONTOLOGY

    # Tier 4: fuzzy title + kind match
    if candidate_kind and candidate_title and entry.kind == candidate_kind:
        if _titles_similar(candidate_title, entry.title):
            return MatchTier.FUZZY

    return None


def _titles_similar(a: str, b: str) -> bool:
    """Simple containment-based title similarity."""
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()
    if a_lower == b_lower:
        return True
    # Require minimum length to avoid false positives on short strings
    if len(a_lower) < 4 or len(b_lower) < 4:
        return False
    return a_lower in b_lower or b_lower in a_lower
