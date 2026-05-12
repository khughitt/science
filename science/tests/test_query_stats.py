"""compute_stats: three independent axes, one row contributes to all three."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

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
    StatsReport,
    compute_stats,
    iter_sidecars,
)


def _ann(
    id_: str,
    *,
    status: Status = Status.OPEN,
    source: str = "lint:bare-author-year-v2026-05-11",
    annotation_type: str = "bare-author-year",
) -> Annotation:
    base = Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="m"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type=annotation_type,
        source=source,
        status=Status.OPEN,
        creator="t",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:d",
        match_text="m",
    )
    if status is Status.OPEN:
        return base
    return replace(
        base,
        status=status,
        modified=datetime(2026, 5, 11, 1, tzinfo=timezone.utc),
        modified_by="t",
    )


def test_empty_corpus_returns_zero_report(tmp_path: Path) -> None:
    sidecars = list(iter_sidecars(tmp_path))
    report = compute_stats(sidecars)
    assert isinstance(report, StatsReport)
    assert report.total_annotations == 0
    assert report.total_sidecars == 0
    assert report.by_status == {}
    assert report.by_source == {}
    assert report.by_type == {}


def test_three_axes_independent(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", status=Status.OPEN, source="lint:foo-v1", annotation_type="bare-author-year"),
        _ann("a-2", status=Status.OPEN, source="lint:foo-v1", annotation_type="bare-author-year"),
        _ann("a-3", status=Status.ACK, source="marker-scanner:phase-2", annotation_type="unverified"),
    )))
    sidecars = list(iter_sidecars(tmp_path))
    report = compute_stats(sidecars)
    assert report.total_annotations == 3
    assert report.total_sidecars == 1
    assert report.by_status == {Status.OPEN: 2, Status.ACK: 1}
    assert report.by_source == {"lint:foo-v1": 2, "marker-scanner:phase-2": 1}
    assert report.by_type == {"bare-author-year": 2, "unverified": 1}


def test_descending_sort_within_each_axis(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", source="lint:c-v1"),
        _ann("a-2", source="lint:b-v1"),
        _ann("a-3", source="lint:b-v1"),
        _ann("a-4", source="lint:a-v1"),
        _ann("a-5", source="lint:a-v1"),
        _ann("a-6", source="lint:a-v1"),
    )))
    sidecars = list(iter_sidecars(tmp_path))
    report = compute_stats(sidecars)
    assert list(report.by_source.items()) == [
        ("lint:a-v1", 3),
        ("lint:b-v1", 2),
        ("lint:c-v1", 1),
    ]


def test_total_sidecars_counts_files(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(_ann("a-1"),)))
    write_sidecar(tmp_path / "b.anno.trig", Sidecar(annotations=(_ann("a-2"),)))
    sidecars = list(iter_sidecars(tmp_path))
    report = compute_stats(sidecars)
    assert report.total_sidecars == 2
    assert report.total_annotations == 2
