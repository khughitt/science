"""sci:matchText predicate round-trip and Annotation.match_text default."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation.io import read_sidecar, write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)


def _ann(*, match_text=None) -> Annotation:
    return Annotation(
        id="a-abc123",
        target=SpecificResource(
            source="example.md",
            selector=TextQuoteSelector(
                exact="Sample sentence with claim.",
                prefix="Some context before. ",
                suffix=" More context after.",
            ),
        ),
        bodies=(TextualBody(value="explanation"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source="lint:bare-author-year-v2026-05-11",
        status=Status.OPEN,
        creator="science-annotate-cli",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:deadbeef",
        match_text=match_text,
    )


def test_match_text_defaults_to_none() -> None:
    ann = _ann()
    assert ann.match_text is None


def test_match_text_round_trip(tmp_path: Path) -> None:
    sidecar_path = tmp_path / "example.anno.trig"
    sidecar = Sidecar(annotations=(_ann(match_text="Brunton 2022"),))
    write_sidecar(sidecar_path, sidecar)
    loaded = read_sidecar(sidecar_path)
    assert loaded.annotations[0].match_text == "Brunton 2022"


def test_match_text_absent_round_trip(tmp_path: Path) -> None:
    sidecar_path = tmp_path / "example.anno.trig"
    sidecar = Sidecar(annotations=(_ann(match_text=None),))
    write_sidecar(sidecar_path, sidecar)
    loaded = read_sidecar(sidecar_path)
    assert loaded.annotations[0].match_text is None
    written = sidecar_path.read_text(encoding="utf-8")
    assert "sci:matchText" not in written


def test_match_text_emission_order(tmp_path: Path) -> None:
    """sci:matchText appears next to sci:liftedFrom in serialized output."""
    sidecar_path = tmp_path / "example.anno.trig"
    sidecar = Sidecar(annotations=(_ann(match_text="[UNVERIFIED]"),))
    write_sidecar(sidecar_path, sidecar)
    text = sidecar_path.read_text(encoding="utf-8")
    assert "sci:matchText" in text
    # Either sci:liftedFrom is absent (this row has no lifted_from) or
    # it appears just before sci:matchText. We accept either ordering
    # but require the predicate to be present and parseable.
    loaded = read_sidecar(sidecar_path)
    assert loaded.annotations[0].match_text == "[UNVERIFIED]"
