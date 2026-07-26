"""Projection for `inquiry show` display: cap each growable list independently.

Lives beside the command, mirroring `explore_ideas_projection.py`. The payload
(`InquiryInfo`) carries four independently growable lists at once --
``related``, ``boundary_in``, ``boundary_out``, ``edges`` -- so the shared
single-list helper (``budget.projection.project_single_list_report``) would
leave three of the four unbounded.
"""

from __future__ import annotations

from typing import Any

INQUIRY_SHOW_LIST_CAP = 40

_GROWABLE_LIST_KEYS = ("related", "boundary_in", "boundary_out", "edges")


def project_inquiry_show(payload: dict[str, Any], cap: int = INQUIRY_SHOW_LIST_CAP) -> dict[str, Any]:
    """Return a display copy with every growable list capped and `<key>_omitted` recorded.

    ``<key>_omitted`` is added only when something was actually withheld, matching the
    shared single-list helper's contract.
    """
    if cap < 0:
        raise ValueError(f"inquiry show cap must be non-negative, got {cap}")
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
