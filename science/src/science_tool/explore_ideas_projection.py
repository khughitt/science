"""Projection for `science explore-ideas apply` display: cap every growable list in the
apply/check-only report independently. Lives beside the command, not in budget/, so the
budgeting mechanism stays free of domain knowledge (mirrors prose_lint_projection.py).

The payload carries several independently growable lists at once (``created``/``to_create``,
``skipped_applied``, ``skipped_other``, ``manual``, ``folds``, ``failures``, ``decision_notes``):
the single-list helper (``budget.projection.project_single_list_report``) would leave every list
but the one it names unbounded, so each is capped here and its own ``<key>_omitted`` recorded.

Every list the apply/check payload grows must be listed in ``_GROWABLE_LIST_KEYS``; a key added
to the payload but not here is silently unbounded.
"""

from __future__ import annotations

from typing import Any

from science_tool.output import summarize_preexisting_warnings

EXPLORE_IDEAS_APPLY_LIST_CAP = 40

_GROWABLE_LIST_KEYS = (
    "created",
    "to_create",
    "skipped_applied",
    "skipped_other",
    "manual",
    "folds",
    "failures",
    "decision_notes",
)


def _project_created_entry(entry: dict[str, Any], *, show_preexisting: bool) -> dict[str, Any]:
    """Summarize one ``created`` entry's pre-existing audit warnings.

    `apply_report` re-runs `_validate_prospective_write` per created candidate, so each of
    up to `EXPLORE_IDEAS_APPLY_LIST_CAP` created entities carries the WHOLE project's
    pre-existing audit warnings (fb-2026-07-25 whole-branch review): capping the ``created``
    list alone leaves each entry's nested ``warnings`` unbounded. Collapse them the same way
    every other write command does.
    """
    warnings = entry.get("warnings")
    if not isinstance(warnings, list):
        return entry
    to_print, note = summarize_preexisting_warnings(warnings, show_preexisting=show_preexisting)
    if note is None:
        return entry
    return {**entry, "warnings": to_print, "preexisting_warnings_note": note}


def project_explore_ideas_apply(
    payload: dict[str, Any], cap: int = EXPLORE_IDEAS_APPLY_LIST_CAP, *, show_preexisting: bool = False
) -> dict[str, Any]:
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
        if key == "created":
            capped = [_project_created_entry(entry, show_preexisting=show_preexisting) for entry in capped]
        projected[key] = capped
        omitted = len(items) - len(capped)
        if omitted:
            projected[f"{key}_omitted"] = omitted
    return projected
