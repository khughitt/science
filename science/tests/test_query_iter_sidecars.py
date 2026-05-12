"""iter_sidecars walks *.anno.trig; wraps parse failures in SidecarParseError."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation.io import write_sidecar
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.query import (
    SidecarParseError,
    iter_sidecars,
)


def _ann(id_: str = "a-abc") -> Annotation:
    return Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="m"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source="lint:bare-author-year-v2026-05-11",
        status=Status.OPEN,
        creator="t",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:d",
        match_text="m",
    )


def test_iter_sidecars_yields_each_file(tmp_path: Path) -> None:
    a = tmp_path / "a.anno.trig"
    write_sidecar(a, Sidecar(annotations=(_ann("a-1"),)))
    sub = tmp_path / "sub"
    sub.mkdir()
    b = sub / "b.anno.trig"
    write_sidecar(b, Sidecar(annotations=(_ann("a-2"),)))

    paths = sorted(p for p, _s in iter_sidecars(tmp_path))
    assert paths == sorted([a, b])


def test_iter_sidecars_skips_non_sidecar_files(tmp_path: Path) -> None:
    write_sidecar(
        tmp_path / "a.anno.trig", Sidecar(annotations=(_ann("a-1"),)),
    )
    (tmp_path / "junk.txt").write_text("nope")
    (tmp_path / "x.trig").write_text("@prefix x: <x> .")  # wrong suffix
    paths = [p for p, _s in iter_sidecars(tmp_path)]
    assert [p.name for p in paths] == ["a.anno.trig"]


def test_iter_sidecars_empty_root_yields_nothing(tmp_path: Path) -> None:
    assert list(iter_sidecars(tmp_path)) == []


def test_iter_sidecars_wraps_parse_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.anno.trig"
    bad.write_text("THIS IS NOT VALID TRIG", encoding="utf-8")
    with pytest.raises(SidecarParseError) as excinfo:
        list(iter_sidecars(tmp_path))
    assert excinfo.value.sidecar_path == bad
    assert excinfo.value.cause is not None
    assert isinstance(excinfo.value.cause, Exception)


def test_iter_sidecars_returns_parsed_sidecar(tmp_path: Path) -> None:
    p = tmp_path / "x.anno.trig"
    write_sidecar(p, Sidecar(annotations=(_ann("a-xyz"),)))
    results = list(iter_sidecars(tmp_path))
    assert len(results) == 1
    _path, sidecar = results[0]
    assert sidecar.annotations[0].id == "a-xyz"


def test_read_sidecar_strict_wraps_parse_error(tmp_path: Path) -> None:
    """Single-file read goes through the same SidecarParseError wrap."""
    from science_tool.annotation.query import read_sidecar_strict

    bad = tmp_path / "bad.anno.trig"
    bad.write_text("THIS IS NOT VALID TRIG", encoding="utf-8")
    with pytest.raises(SidecarParseError) as excinfo:
        read_sidecar_strict(bad)
    assert excinfo.value.sidecar_path == bad
    assert isinstance(excinfo.value.cause, Exception)


def test_read_sidecar_strict_returns_parsed(tmp_path: Path) -> None:
    from science_tool.annotation.query import read_sidecar_strict

    p = tmp_path / "x.anno.trig"
    write_sidecar(p, Sidecar(annotations=(_ann("a-good"),)))
    sidecar = read_sidecar_strict(p)
    assert sidecar.annotations[0].id == "a-good"
