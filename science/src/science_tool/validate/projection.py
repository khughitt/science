"""Projection for `science validate` display: cap the growable findings list, leaving the
summary counts and exit-determining totals to the full result."""

from __future__ import annotations

from typing import Any

VALIDATE_ROW_CAP = 40


def project_validate_results(results: list[Any], cap: int = VALIDATE_ROW_CAP) -> tuple[list[Any], int]:
    """Return (capped_results, omitted_count)."""
    if cap < 0:
        raise ValueError(f"validate cap must be non-negative, got {cap}")
    capped = results[:cap]
    return capped, len(results) - len(capped)
