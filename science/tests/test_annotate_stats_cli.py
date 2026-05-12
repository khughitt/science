"""science annotate stats: three sections, table + json."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
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


def _ann(
    id_: str, *,
    status: Status = Status.OPEN,
    source: str = "lint:foo-v1",
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
        base, status=status,
        modified=datetime(2026, 5, 11, 1, tzinfo=timezone.utc),
        modified_by="t",
    )


def test_stats_empty_corpus(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["stats", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "0 annotation" in result.output


def test_stats_table_sections(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", status=Status.OPEN, source="lint:foo-v1", annotation_type="bare-author-year"),
        _ann("a-2", status=Status.OPEN, source="lint:foo-v1", annotation_type="bare-author-year"),
        _ann("a-3", status=Status.ACK, source="marker-scanner:phase-2", annotation_type="unverified"),
    )))
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["stats", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "By status" in result.output
    assert "By source" in result.output
    assert "By type" in result.output
    assert "open" in result.output
    assert "ack" in result.output
    assert "lint:foo-v1" in result.output
    assert "marker-scanner:phase-2" in result.output
    assert "bare-author-year" in result.output


def test_stats_json_schema(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1"),
    )))
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "stats", "--root", str(tmp_path), "--format", "json",
    ])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["total_annotations"] == 1
    assert payload["summary"]["total_sidecars"] == 1
    assert payload["by_status"] == {"open": 1}
    assert payload["by_source"] == {"lint:foo-v1": 1}
    assert payload["by_type"] == {"bare-author-year": 1}


def test_stats_descending_order_in_json(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", source="lint:c-v1"),
        _ann("a-2", source="lint:a-v1"),
        _ann("a-3", source="lint:a-v1"),
        _ann("a-4", source="lint:a-v1"),
        _ann("a-5", source="lint:b-v1"),
        _ann("a-6", source="lint:b-v1"),
    )))
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "stats", "--root", str(tmp_path), "--format", "json",
    ])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    keys = list(payload["by_source"].keys())
    assert keys == ["lint:a-v1", "lint:b-v1", "lint:c-v1"]
