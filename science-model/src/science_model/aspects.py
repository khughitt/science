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


class AspectValidationError(ValueError):
    """Raised when entity aspects are invalid for a project."""


def validate_entity_aspects(
    entity_aspects: list[str],
    project_aspects: list[str],
) -> list[str]:
    """Validate explicit entity aspects and return them in canonical order.

    Invariants enforced:
    - Non-empty list.
    - No duplicates.
    - Every entry is a member of ``KNOWN_ASPECTS``.
    - Every entry is declared in ``project_aspects``.

    Returns the canonicalized list: same values, reordered to match
    ``project_aspects`` ordering for stable diffs.
    """
    if not entity_aspects:
        raise AspectValidationError(
            "Entity aspects list is empty; use absent field to inherit."
        )
    seen: set[str] = set()
    for aspect in entity_aspects:
        if aspect in seen:
            raise AspectValidationError(f"duplicate aspect: {aspect!r}")
        seen.add(aspect)
        if aspect not in KNOWN_ASPECTS:
            raise AspectValidationError(
                f"{aspect!r} is not in the aspect vocabulary "
                f"({sorted(KNOWN_ASPECTS)})."
            )
        if aspect not in project_aspects:
            raise AspectValidationError(
                f"{aspect!r} is not declared in project aspects "
                f"({project_aspects}); add it to science.yaml first."
            )
    return [a for a in project_aspects if a in seen]
