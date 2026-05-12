"""merge_planned cross-source contamination raises ValueError, not AssertionError."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from science_tool.annotation.audit import merge_planned
from science_tool.annotation.model import (
    Motivation,
    Sidecar,
    SpecificResource,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.sources.base import PlannedAnnotation


def _planned(source_name: str, exact: str = "x") -> PlannedAnnotation:
    return PlannedAnnotation(
        target=SpecificResource(
            source="example.md",
            selector=TextQuoteSelector(exact=exact, prefix="", suffix=""),
        ),
        annotation_type="bare-author-year",
        motivation=Motivation.CLASSIFYING,
        body=TextualBody(value="msg"),
        match_text="m",
        source_name=source_name,
    )


def test_merge_planned_rejects_mixed_sources_with_value_error() -> None:
    sidecar = Sidecar()
    planned = [
        _planned("lint:foo-v1", exact="a"),
        _planned("lint:bar-v1", exact="b"),
    ]
    with pytest.raises(ValueError, match="single-source"):
        merge_planned(
            sidecar, planned,
            actor="test", now=datetime(2026, 5, 11, tzinfo=timezone.utc),
        )
