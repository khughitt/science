"""Smoke test for the SourceAdapter protocol + IdCollisionError shape."""

from __future__ import annotations

import pytest

from science_tool.annotation.model import (
    Motivation, SpecificResource, TextQuoteSelector, TextualBody,
)
from science_tool.annotation.sources.base import (
    IdCollisionError,
    PlannedAnnotation,
)


def test_planned_annotation_construction() -> None:
    p = PlannedAnnotation(
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="abc", prefix="", suffix=""),
        ),
        annotation_type="bare-author-year",
        motivation=Motivation.CLASSIFYING,
        body=TextualBody(value="msg"),
        match_text="Brunton 2022",
        source_name="lint:bare-author-year-v2026-05-11",
    )
    assert p.lifted_from is None
    assert p.match_text == "Brunton 2022"


def test_id_collision_error_carries_message() -> None:
    err = IdCollisionError("boom")
    assert "boom" in str(err)
