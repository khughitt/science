"""filter_annotations: status / source-glob / since predicates AND together."""

from __future__ import annotations

from dataclasses import replace
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
    filter_annotations,
    iter_sidecars,
)


def _ann(
    id_: str,
    *,
    status: Status = Status.OPEN,
    source: str = "lint:bare-author-year-v2026-05-11",
) -> Annotation:
    base = Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="m"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
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


def _setup(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", status=Status.OPEN),
        _ann("a-2", status=Status.ACK),
        _ann("a-3", status=Status.SUPERSEDED),
        _ann("a-4", source="marker-scanner:phase-2"),
        _ann("a-5", source="lint:short-form-ids-v2026-05-11"),
    )))


# ---- status filter --------------------------------------------------

def test_status_filter_default_open_only(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(sidecars, statuses=frozenset({Status.OPEN})))
    ids = sorted(a.id for _p, a in rows)
    assert ids == ["a-1", "a-4", "a-5"]


def test_status_filter_multi(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars, statuses=frozenset({Status.OPEN, Status.ACK}),
    ))
    assert sorted(a.id for _p, a in rows) == ["a-1", "a-2", "a-4", "a-5"]


def test_status_filter_none_means_all(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(sidecars, statuses=None))
    assert sorted(a.id for _p, a in rows) == [
        "a-1", "a-2", "a-3", "a-4", "a-5",
    ]


# ---- source filter (glob) -------------------------------------------

def test_source_filter_exact(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars,
        statuses=None,
        sources=("marker-scanner:phase-2",),
    ))
    assert [a.id for _p, a in rows] == ["a-4"]


def test_source_filter_glob(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars, statuses=None, sources=("lint:*",),
    ))
    assert sorted(a.id for _p, a in rows) == ["a-1", "a-2", "a-3", "a-5"]


def test_source_filter_multi_pattern_or(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars,
        statuses=None,
        sources=("marker-scanner:*", "lint:short-form-ids-*"),
    ))
    assert sorted(a.id for _p, a in rows) == ["a-4", "a-5"]


# ---- since_changed filter -------------------------------------------

def test_since_filter_excludes_unchanged(tmp_path: Path) -> None:
    _setup(tmp_path)
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars,
        statuses=None,
        since_changed=frozenset(),
    ))
    assert rows == []


def test_since_filter_includes_changed_md(tmp_path: Path) -> None:
    _setup(tmp_path)
    md_path = (tmp_path / "a.md").resolve()
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars,
        statuses=None,
        since_changed=frozenset({md_path}),
    ))
    assert len(rows) == 5


# ---- AND across predicates ------------------------------------------

def test_and_across_predicates(tmp_path: Path) -> None:
    _setup(tmp_path)
    md_path = (tmp_path / "a.md").resolve()
    sidecars = list(iter_sidecars(tmp_path))
    rows = list(filter_annotations(
        sidecars,
        statuses=frozenset({Status.OPEN}),
        sources=("lint:bare-author-year-*",),
        since_changed=frozenset({md_path}),
    ))
    assert [a.id for _p, a in rows] == ["a-1"]


def test_git_changed_markdown_returns_paths(tmp_path: Path, monkeypatch) -> None:
    """git_changed_markdown shells out and returns absolute markdown paths."""
    from science_tool.annotation import query

    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["cwd"] = kwargs.get("cwd")

        class R:
            returncode = 0
            stdout = "notes/foo.md\nappendix/bar.md\nREADME\n"
            stderr = ""

        return R()

    monkeypatch.setattr(query, "_run_git", fake_run)
    out = query.git_changed_markdown(tmp_path, "main")
    assert out == frozenset({
        (tmp_path / "notes/foo.md").resolve(),
        (tmp_path / "appendix/bar.md").resolve(),
    })
    assert captured["args"] == [
        "git", "diff", "--name-only", "main...", "--", "*.md",
    ]


def test_git_changed_markdown_non_repo_raises(tmp_path: Path, monkeypatch) -> None:
    from science_tool.annotation import query

    def fake_run(args, **kwargs):
        class R:
            returncode = 128
            stdout = ""
            stderr = "fatal: not a git repository"

        return R()

    monkeypatch.setattr(query, "_run_git", fake_run)
    with pytest.raises(RuntimeError, match="not a git repository"):
        query.git_changed_markdown(tmp_path, "main")
