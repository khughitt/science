"""Projection for `science explore-ideas apply` display: cap every growable list in the
apply/check-only report independently. Lives beside the command, not in budget/, so the
budgeting mechanism stays free of domain knowledge (mirrors prose_lint_projection.py).

The payload carries several independently growable lists at once (``created``/``to_create``,
``skipped_applied``, ``skipped_other``, ``manual``, ``folds``, ``failures``): the single-list
helper (``budget.projection.project_single_list_report``) would leave every list but the one
it names unbounded, so each is capped here and its own ``<key>_omitted`` recorded.
"""

from __future__ import annotations

from typing import Any

EXPLORE_IDEAS_APPLY_LIST_CAP = 40

_GROWABLE_LIST_KEYS = (
    "created",
    "to_create",
    "skipped_applied",
    "skipped_other",
    "manual",
    "folds",
    "failures",
)


def project_explore_ideas_apply(payload: dict[str, Any], cap: int = EXPLORE_IDEAS_APPLY_LIST_CAP) -> dict[str, Any]:
    """Return a display copy with every growable list capped and `<key>_omitted` recorded.

    Only keys actually present in ``payload`` are projected: the check-only payload has no
    ``created``/``failures``, and the apply payload has no ``to_create``. ``report`` and any
    other non-list key pass through untouched.
    """
    if cap < 0:
        raise ValueError(f"explore-ideas apply cap must be non-negative, got {cap}")
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
