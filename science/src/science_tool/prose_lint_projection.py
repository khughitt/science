"""Projection for `science prose lint` display. Narrows the growable `hits` list without
changing the summary the report claims. Lives beside the command, not in budget/, so the
budgeting mechanism stays free of domain knowledge (mirrors graph/health_projection.py)."""

from __future__ import annotations

from typing import Any

PROSE_LINT_ROW_CAP = 40


def project_prose_lint(payload: dict[str, Any], cap: int = PROSE_LINT_ROW_CAP) -> dict[str, Any]:
    """Return a display copy with `hits` capped and `hits_omitted` recorded.

    `counts` and `coverage` are copied through untouched: they are the summary, and
    redefining them from the capped list would make the report understate its own findings.
    """
    if cap < 0:
        raise ValueError(f"prose lint cap must be non-negative, got {cap}")
    hits = payload["hits"]
    capped = hits[:cap]
    return {
        **payload,
        "hits": capped,
        "hits_omitted": len(hits) - len(capped),
    }
