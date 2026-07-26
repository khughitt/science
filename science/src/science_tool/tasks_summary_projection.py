"""Projection for `tasks summary` display: cap each distinct-value breakdown independently.

Lives beside the command, mirroring `dag/audit_projection.py`. The report carries four
independently growable mappings at once -- ``by_status``, ``by_type``, ``by_priority``, and
``by_group`` (one member per distinct value seen across active tasks) -- so the single-list
helper (``budget.projection.project_single_list_report``) only knows how to cap one
top-level *list*, and would leave three of the four unbounded here.
"""

from __future__ import annotations

from typing import Any

TASKS_SUMMARY_BREAKDOWN_CAP = 40

_BREAKDOWN_KEYS = ("by_status", "by_type", "by_priority", "by_group")


def project_tasks_summary(payload: dict[str, Any], cap: int = TASKS_SUMMARY_BREAKDOWN_CAP) -> dict[str, Any]:
    """Return a display copy with each breakdown mapping capped to its first ``cap`` items.

    Caps in sorted-key order, matching the command's own sort of each breakdown before
    display. ``<key>_omitted`` is recorded only when something was actually withheld --
    absence of the marker means "nothing dropped", matching the shared single-list helper's
    contract. ``total`` is passed through untouched: it is the summary, and recomputing it
    from a capped breakdown would make the report understate its own findings.
    """
    if cap < 0:
        raise ValueError(f"tasks summary cap must be non-negative, got {cap}")

    projected = dict(payload)
    for key in _BREAKDOWN_KEYS:
        items = sorted(payload[key].items())
        capped_items = items[:cap]
        projected[key] = dict(capped_items)
        omitted = len(items) - len(capped_items)
        if omitted:
            projected[f"{key}_omitted"] = omitted
    return projected
