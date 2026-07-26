"""Semantic narrowing of row-shaped payloads, before serialization.

Projection runs early precisely so the omitted count is known and can travel inside the
payload. After rendering there are only characters.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

RowT = TypeVar("RowT")


@dataclass(frozen=True)
class ProjectedRows(Generic[RowT]):
    """Generic over the row type.

    ``tasks list`` projects ``Task`` models for its table branch and dicts for its JSON
    branch; a ``Mapping``-only signature would be a type error at the first call site.

    ``TypeVar`` + ``Generic`` rather than PEP 695 ``class ProjectedRows[T]``: the packages
    declare ``requires-python = ">=3.11"`` and Pyright is pinned to 3.11, where the PEP 695
    form is a syntax-level error. ``output.py:15`` and ``instruments.py:31`` use the same
    construction.
    """

    rows: list[RowT]
    omitted: int
    total: int

    @property
    def truncated(self) -> bool:
        return self.omitted > 0


def project_rows(rows: Sequence[RowT], max_rows: int | None) -> ProjectedRows[RowT]:
    """Keep the first ``max_rows`` in caller order, reporting how many were dropped.

    Caller order is preserved rather than re-sorted: the command already sorted for a
    reason, and re-sorting here would make the truncated view disagree with the complete
    one.
    """
    if max_rows is not None and max_rows < 0:
        raise ValueError("max_rows must be non-negative")

    total = len(rows)
    if max_rows is None or total <= max_rows:
        return ProjectedRows(rows=list(rows), omitted=0, total=total)
    return ProjectedRows(rows=list(rows[:max_rows]), omitted=total - max_rows, total=total)


def project_single_list_report(payload: Mapping[str, Any], list_key: str, cap: int) -> dict[str, Any]:
    """Cap the one growable list in a summary+list REPORT payload, recording what was dropped.

    Returns a display copy in which ``payload[list_key]`` is capped to the first ``cap`` items
    and a sibling ``f"{list_key}_omitted"`` records how many were withheld. Every other key --
    the report's summary/counts -- is passed through untouched: recomputing a summary from the
    capped list would make the report understate its own findings. This mirrors the bespoke
    ``prose_lint_projection`` / ``graph.health_projection`` projectors, generalized for the
    common REPORT shape of a summary plus exactly one growable list. A report with more than
    one growable list needs a bespoke projector instead -- this helper would silently leave the
    others unbounded.
    """
    if cap < 0:
        raise ValueError(f"cap must be non-negative, got {cap}")
    if list_key not in payload:
        raise KeyError(f"payload has no list at key {list_key!r}")
    items = payload[list_key]
    capped = list(items[:cap])
    return {**payload, list_key: capped, f"{list_key}_omitted": len(items) - len(capped)}
