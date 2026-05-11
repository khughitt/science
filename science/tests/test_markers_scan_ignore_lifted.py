"""markers scan --ignore-lifted post-filter behavior."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group
from science_tool.markers_cli import markers_group

FX = Path(__file__).parent / "_fixtures" / "annotation" / "audit"


@pytest.fixture
def workspace_with_lifted(tmp_path: Path) -> Path:
    doc = tmp_path / "doc"
    doc.mkdir()
    shutil.copy(FX / "mixed-tokens.md", doc / "mixed-tokens.md")
    runner = CliRunner()
    runner.invoke(annotate_group, [
        "lift-tokens", "--root", str(tmp_path), "--actor", "tester",
    ])
    return tmp_path


def test_ignore_lifted_skips_lifted_hits(workspace_with_lifted: Path) -> None:
    runner = CliRunner()
    plain = runner.invoke(markers_group, [
        "scan", "--root", str(workspace_with_lifted), "--format", "json",
    ])
    filtered = runner.invoke(markers_group, [
        "scan", "--root", str(workspace_with_lifted),
        "--ignore-lifted", "--format", "json",
    ])
    plain_payload = json.loads(plain.output)
    filtered_payload = json.loads(filtered.output)
    assert sum(plain_payload["counts"].values()) > 0
    assert filtered_payload["counts"] == {}


def test_no_sidecar_means_no_skip(tmp_path: Path) -> None:
    doc = tmp_path / "doc"
    doc.mkdir()
    shutil.copy(FX / "mixed-tokens.md", doc / "mixed-tokens.md")
    runner = CliRunner()
    plain = runner.invoke(markers_group, [
        "scan", "--root", str(tmp_path), "--format", "json",
    ])
    filtered = runner.invoke(markers_group, [
        "scan", "--root", str(tmp_path),
        "--ignore-lifted", "--format", "json",
    ])
    assert plain.output == filtered.output


def test_ignore_lifted_preserves_unrelated_hits(tmp_path: Path) -> None:
    """A row with non-matching lifted_from in sidecar does not skip the hit."""
    doc = tmp_path / "doc"
    doc.mkdir()
    md = doc / "mixed-tokens.md"
    shutil.copy(FX / "mixed-tokens.md", md)
    sidecar = doc / "mixed-tokens.anno.trig"
    sidecar.write_text(
        '@prefix oa: <http://www.w3.org/ns/oa#> .\n'
        '@prefix sci: <http://example.org/science/vocab/> .\n'
        '@prefix anno: <#> .\n'
        '@prefix dc:  <http://purl.org/dc/terms/> .\n'
        '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n'
        'anno:annotations {\n'
        '  anno:a-other a oa:Annotation ;\n'
        '    oa:hasTarget [ oa:hasSource <mixed-tokens.md> ; '
        'oa:hasSelector [ a oa:TextQuoteSelector ; '
        'oa:exact "irrelevant" ; oa:prefix "" ; oa:suffix "" ] ] ;\n'
        '    oa:hasBody [ a oa:TextualBody ; dc:format "text/plain" ; '
        '<http://www.w3.org/1999/02/22-rdf-syntax-ns#value> "x" ] ;\n'
        '    oa:motivatedBy oa:commenting ;\n'
        '    sci:annotationType "comment" ;\n'
        '    sci:source "human:keith" ;\n'
        '    sci:status "open" ;\n'
        '    sci:liftedFrom "[NEVER]" ;\n'
        '    sci:matchText "[NEVER]" ;\n'
        '    dc:creator "k" ;\n'
        '    dc:created "2026-05-11T00:00:00+00:00"^^xsd:dateTime .\n'
        '}\n',
        encoding="utf-8",
    )
    runner = CliRunner()
    filtered = runner.invoke(markers_group, [
        "scan", "--root", str(tmp_path),
        "--ignore-lifted", "--format", "json",
    ])
    payload = json.loads(filtered.output)
    assert sum(payload["counts"].values()) > 0
