# science/src/science_tool/annotation/sources/__init__.py
"""Annotation source adapters.

Each adapter scans a markdown file and emits PlannedAnnotation
records consumed by `annotation.audit.merge_planned`. See
docs/conventions/annotation-tokens.md for marker-token behavior.
"""

from __future__ import annotations

from science_tool.annotation.sources.base import (
    IdCollisionError,
    PlannedAnnotation,
    SourceAdapter,
)
from science_tool.annotation.sources.lint import (
    bare_author_year_source,
    numeric_anchor_source,
    short_form_ids_source,
)
from science_tool.annotation.sources.marker_token import MarkerTokenSource

SOURCES: dict[str, SourceAdapter] = {
    "marker-token":     MarkerTokenSource(),
    "bare-author-year": bare_author_year_source(),
    "short-form-ids":   short_form_ids_source(),
    "numeric-anchor":   numeric_anchor_source(),
}

LINT_SOURCES: tuple[str, ...] = (
    "bare-author-year",
    "short-form-ids",
    "numeric-anchor",
)

__all__ = [
    "IdCollisionError",
    "LINT_SOURCES",
    "PlannedAnnotation",
    "SOURCES",
    "SourceAdapter",
]
