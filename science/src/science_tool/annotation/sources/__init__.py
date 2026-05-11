# science/src/science_tool/annotation/sources/__init__.py
"""Annotation source adapters.

Each adapter scans a markdown file and emits PlannedAnnotation
records consumed by `annotation.audit.merge_planned`. See spec
docs/plans/2026-05-11-annotation-system-p3.2-spec.md §Module layout.
"""

from __future__ import annotations

from science_tool.annotation.sources.base import (
    IdCollisionError,
    PlannedAnnotation,
    SourceAdapter,
)

__all__ = ["IdCollisionError", "PlannedAnnotation", "SourceAdapter"]
