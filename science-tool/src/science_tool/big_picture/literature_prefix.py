"""Transition-window canonicalization for external-literature entity IDs.

During the window between the manuscript+paper rename shipping and every
tracked project completing its migration, downstream consumers must treat
``article:<bibkey>`` as a legacy alias of canonical ``paper:<bibkey>``.
This helper is the single place that encodes that rule.

Removal: this module is deleted (one-line change per consumer) once all
tracked projects confirm migration. See
docs/specs/2026-04-19-manuscript-paper-rename-design.md §Transition-Window.
"""

from __future__ import annotations

_LEGACY_EXTERNAL_PREFIX = "article:"
_CANONICAL_EXTERNAL_PREFIX = "paper:"


def canonical_paper_id(entity_id: str) -> str:
    """Return the canonical form of ``entity_id``.

    Maps ``article:<X>`` → ``paper:<X>``. All other entity IDs pass through.
    """
    if entity_id.startswith(_LEGACY_EXTERNAL_PREFIX):
        return _CANONICAL_EXTERNAL_PREFIX + entity_id[len(_LEGACY_EXTERNAL_PREFIX) :]
    return entity_id


def is_external_paper_id(entity_id: str) -> bool:
    """True iff ``entity_id`` denotes an external literature entity."""
    return entity_id.startswith((_CANONICAL_EXTERNAL_PREFIX, _LEGACY_EXTERNAL_PREFIX))
