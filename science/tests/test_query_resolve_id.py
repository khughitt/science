"""resolve_id covers bare frag, bare-stem qualifier, rel-path qualifier."""

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
    AmbiguousAnnotationId,
    AnnotationNotFound,
    ResolvedAnnotation,
    resolve_id,
)


def _ann(id_: str) -> Annotation:
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


def _make(root: Path, relpath: str, ann_ids: list[str]) -> Path:
    p = root / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    write_sidecar(p, Sidecar(annotations=tuple(_ann(i) for i in ann_ids)))
    return p


# ---- Bare frag ------------------------------------------------------

def test_bare_frag_unique(tmp_path: Path) -> None:
    sidecar = _make(tmp_path, "foo.anno.trig", ["a-aaa"])
    resolved = resolve_id(tmp_path, "a-aaa")
    assert isinstance(resolved, ResolvedAnnotation)
    assert resolved.sidecar_path == sidecar
    assert resolved.annotation.id == "a-aaa"
    assert resolved.entity_stem == "foo"
    assert resolved.entity_relpath == "foo"


def test_bare_frag_ambiguous_lists_relpath_candidates(tmp_path: Path) -> None:
    _make(tmp_path, "notes/foo.anno.trig", ["a-aaa"])
    _make(tmp_path, "appendix/foo.anno.trig", ["a-aaa"])
    with pytest.raises(AmbiguousAnnotationId) as excinfo:
        resolve_id(tmp_path, "a-aaa")
    assert sorted(excinfo.value.candidates) == [
        "appendix/foo:a-aaa",
        "notes/foo:a-aaa",
    ]


def test_bare_frag_not_found(tmp_path: Path) -> None:
    _make(tmp_path, "foo.anno.trig", ["a-aaa"])
    with pytest.raises(AnnotationNotFound):
        resolve_id(tmp_path, "a-zzz")


# ---- Bare-stem qualifier --------------------------------------------

def test_bare_stem_qualifier_unique(tmp_path: Path) -> None:
    _make(tmp_path, "foo.anno.trig", ["a-aaa"])
    resolved = resolve_id(tmp_path, "foo:a-aaa")
    assert resolved.annotation.id == "a-aaa"
    assert resolved.entity_stem == "foo"


def test_bare_stem_qualifier_ambiguous_lists_relpaths(tmp_path: Path) -> None:
    _make(tmp_path, "notes/foo.anno.trig", ["a-bbb"])
    _make(tmp_path, "appendix/foo.anno.trig", ["a-bbb"])
    with pytest.raises(AmbiguousAnnotationId) as excinfo:
        resolve_id(tmp_path, "foo:a-bbb")
    assert sorted(excinfo.value.candidates) == [
        "appendix/foo:a-bbb",
        "notes/foo:a-bbb",
    ]


def test_bare_stem_qualifier_missing_sidecar(tmp_path: Path) -> None:
    _make(tmp_path, "foo.anno.trig", ["a-aaa"])
    with pytest.raises(AnnotationNotFound):
        resolve_id(tmp_path, "missing:a-aaa")


def test_bare_stem_qualifier_missing_frag(tmp_path: Path) -> None:
    _make(tmp_path, "foo.anno.trig", ["a-aaa"])
    with pytest.raises(AnnotationNotFound):
        resolve_id(tmp_path, "foo:a-zzz")


# ---- Rel-path qualifier ---------------------------------------------

def test_rel_path_qualifier_hit(tmp_path: Path) -> None:
    sidecar = _make(tmp_path, "notes/foo.anno.trig", ["a-aaa"])
    resolved = resolve_id(tmp_path, "notes/foo:a-aaa")
    assert resolved.sidecar_path == sidecar
    assert resolved.entity_relpath == "notes/foo"


def test_rel_path_qualifier_disambiguates(tmp_path: Path) -> None:
    _make(tmp_path, "notes/foo.anno.trig", ["a-bbb"])
    _make(tmp_path, "appendix/foo.anno.trig", ["a-bbb"])
    resolved = resolve_id(tmp_path, "notes/foo:a-bbb")
    assert resolved.entity_relpath == "notes/foo"


def test_rel_path_qualifier_missing_sidecar(tmp_path: Path) -> None:
    with pytest.raises(AnnotationNotFound):
        resolve_id(tmp_path, "notes/missing:a-aaa")


# ---- Returned sidecar is the parsed sidecar (not a re-read) ---------

def test_resolved_carries_full_sidecar(tmp_path: Path) -> None:
    _make(tmp_path, "foo.anno.trig", ["a-aaa", "a-bbb"])
    resolved = resolve_id(tmp_path, "a-aaa")
    assert {a.id for a in resolved.sidecar.annotations} == {"a-aaa", "a-bbb"}
