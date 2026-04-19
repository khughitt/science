"""Shared aspect vocabulary, resolution, validation, and filtering helpers.

Entity-level `aspects:` uses the same vocabulary as project-level `aspects:` in
science.yaml. This module is the single source of truth for that vocabulary
and for the resolution/filter rules; commands consume it rather than
reimplementing aspect logic.
"""
from __future__ import annotations

KNOWN_ASPECTS: frozenset[str] = frozenset(
    {
        "causal-modeling",
        "hypothesis-testing",
        "computational-analysis",
        "software-development",
    }
)

SOFTWARE_ASPECT: str = "software-development"


def resolve_entity_aspects(
    entity_aspects: list[str] | None,
    project_aspects: list[str],
) -> list[str]:
    """Return the effective aspect list for an entity.

    - If ``entity_aspects`` is None (absent), inherit ``project_aspects``.
    - If ``entity_aspects`` is a non-empty list, return it unchanged.
    - Callers are responsible for having validated ``entity_aspects`` before
      resolution; this function does not re-validate.
    """
    if entity_aspects is None:
        return list(project_aspects)
    return list(entity_aspects)


def matches_aspect_filter(resolved: list[str], filter_set: set[str]) -> bool:
    """Return True iff ``resolved`` intersects ``filter_set``.

    The sole aspect-filter rule used by downstream commands. Callers choose
    ``filter_set``; this helper does not invent the filter.
    """
    return bool(set(resolved) & filter_set)
