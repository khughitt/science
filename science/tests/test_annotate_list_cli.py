"""science annotate list: PATH modes + filters + format."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
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


def _ann(id_: str, status: Status = Status.OPEN, source: str = "lint:foo-v1") -> Annotation:
    from dataclasses import replace
    base = Annotation(
        id=id_,
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(
                exact="A short sample sentence.",
                prefix="Before. ",
                suffix=" After.",
            ),
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


# ---- happy path: bare list ------------------------------------------

def test_list_default_open_only(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", status=Status.OPEN),
        _ann("a-2", status=Status.ACK),
    )))
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "a-1" in result.output
    assert "a-2" not in result.output


def test_list_status_all(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", status=Status.OPEN),
        _ann("a-2", status=Status.ACK),
    )))
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "list", "--root", str(tmp_path), "--status", "all",
    ])
    assert result.exit_code == 0
    assert "a-1" in result.output
    assert "a-2" in result.output


def test_list_source_glob(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(
        _ann("a-1", source="lint:foo-v1"),
        _ann("a-2", source="marker-scanner:phase-2"),
    )))
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "list", "--root", str(tmp_path), "--source", "lint:*",
    ])
    assert result.exit_code == 0
    assert "a-1" in result.output
    assert "a-2" not in result.output


def test_list_json_format(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(_ann("a-1"),)))
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "list", "--root", str(tmp_path), "--format", "json",
    ])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["total_annotations"] == 1
    assert payload["annotations"][0]["id"] == "a-1"


# ---- PATH modes -----------------------------------------------------

def test_list_path_directory(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    write_sidecar(sub / "a.anno.trig", Sidecar(annotations=(_ann("a-1"),)))
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", str(sub)])
    assert result.exit_code == 0
    assert "a-1" in result.output


def test_list_path_markdown(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "foo.anno.trig", Sidecar(annotations=(_ann("a-1"),)))
    md = tmp_path / "foo.md"
    md.write_text("body", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", str(md)])
    assert result.exit_code == 0
    assert "a-1" in result.output


def test_list_path_sidecar(tmp_path: Path) -> None:
    sidecar = tmp_path / "foo.anno.trig"
    write_sidecar(sidecar, Sidecar(annotations=(_ann("a-1"),)))
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", str(sidecar)])
    assert result.exit_code == 0
    assert "a-1" in result.output


def test_list_path_missing_md_is_empty(tmp_path: Path) -> None:
    """Markdown PATH with no sidecar yields empty result, exit 0."""
    md = tmp_path / "nope.md"
    md.write_text("body", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", str(md)])
    assert result.exit_code == 0
    assert "0 annotation" in result.output


def test_list_path_md_with_corrupt_sidecar_friendly_error(tmp_path: Path) -> None:
    """PATH=foo.md with corrupt foo.anno.trig produces ClickException, not raw rdflib trace."""
    md = tmp_path / "foo.md"
    md.write_text("body", encoding="utf-8")
    sidecar = tmp_path / "foo.anno.trig"
    sidecar.write_text("THIS IS NOT VALID TRIG", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", str(md)])
    assert result.exit_code == 1
    assert "foo.anno.trig" in result.output


def test_list_path_anno_trig_corrupt_friendly_error(tmp_path: Path) -> None:
    """PATH=foo.anno.trig (corrupt) produces ClickException, not raw rdflib trace."""
    sidecar = tmp_path / "foo.anno.trig"
    sidecar.write_text("THIS IS NOT VALID TRIG", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(annotate_group, ["list", str(sidecar)])
    assert result.exit_code == 1
    assert "foo.anno.trig" in result.output


def test_list_root_and_path_mutually_exclusive(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "list", "--root", str(tmp_path), str(tmp_path),
    ])
    assert result.exit_code == 1
    assert "mutually exclusive" in result.output


# ---- since plumbing -------------------------------------------------

def test_list_since_outside_repo_errors(tmp_path: Path) -> None:
    write_sidecar(tmp_path / "a.anno.trig", Sidecar(annotations=(_ann("a-1"),)))
    runner = CliRunner()
    result = runner.invoke(annotate_group, [
        "list", "--root", str(tmp_path), "--since", "main",
    ])
    assert result.exit_code == 1
    assert "git" in result.output.lower()
