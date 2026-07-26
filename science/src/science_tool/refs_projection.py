"""Projection for `refs check` display: cap `broken` and `markers` independently.

Lives beside the command, mirroring `explore_ideas_projection.py`. The payload carries two
independently growable lists at once (`broken`, `markers`) -- and `--summary-only` omits
both entirely -- so the shared single-list helper (`budget.projection.project_single_list_report`)
would either leave one list unbounded or choke on a missing key.
"""

from __future__ import annotations

from typing import Any

REFS_CHECK_LIST_CAP = 40

_GROWABLE_LIST_KEYS = ("broken", "markers")


def project_refs_check(payload: dict[str, Any], cap: int = REFS_CHECK_LIST_CAP) -> dict[str, Any]:
    """Return a display copy with `broken` and `markers` (when present) each capped.

    Only keys actually present in ``payload`` are projected: `--summary-only` payloads carry
    neither list. `<key>_omitted` is added only when something was actually withheld.
    """
    if cap < 0:
        raise ValueError(f"refs check cap must be non-negative, got {cap}")
    projected = dict(payload)
    for key in _GROWABLE_LIST_KEYS:
        if key not in payload:
            continue
        items = payload[key]
        capped = list(items[:cap])
        projected[key] = capped
        omitted = len(items) - len(capped)
        if omitted:
            projected[f"{key}_omitted"] = omitted
    return projected
