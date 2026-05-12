"""atomic_write_text and serialize_sidecar are public io.py helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from science_tool.annotation.io import (
    atomic_write_text,
    read_sidecar,
    serialize_sidecar,
)
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)


def _ann() -> Annotation:
    return Annotation(
        id="a-abc123",
        target=SpecificResource(
            source="example.md",
            selector=TextQuoteSelector(
                exact="Sample sentence.",
                prefix="Before. ",
                suffix=" After.",
            ),
        ),
        bodies=(TextualBody(value="msg"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source="lint:bare-author-year-v2026-05-11",
        status=Status.OPEN,
        creator="test",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:dead",
        match_text="x",
    )


def test_atomic_write_text_writes_and_replaces(tmp_path: Path) -> None:
    target = tmp_path / "x.txt"
    target.write_text("old", encoding="utf-8")
    atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_atomic_write_text_no_orphan_temp_on_success(tmp_path: Path) -> None:
    target = tmp_path / "x.txt"
    atomic_write_text(target, "hello")
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "x.txt"]
    assert leftovers == [], f"unexpected temp leftovers: {leftovers!r}"


def test_serialize_sidecar_round_trips(tmp_path: Path) -> None:
    original = Sidecar(annotations=(_ann(),))
    text = serialize_sidecar(original)
    target = tmp_path / "x.anno.trig"
    target.write_text(text, encoding="utf-8")
    loaded = read_sidecar(target)
    assert loaded.annotations[0].id == "a-abc123"


def test_serialize_sidecar_returns_str() -> None:
    text = serialize_sidecar(Sidecar(annotations=(_ann(),)))
    assert isinstance(text, str)
    assert "@prefix" in text
