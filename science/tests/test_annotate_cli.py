"""CLI tests for `science annotate verify`."""

from __future__ import annotations

import shutil
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group

FIX = Path(__file__).parent / "_fixtures" / "annotation" / "verify"


def _seed(tmp_path: Path) -> Path:
    work = tmp_path / "project"
    shutil.copytree(FIX, work)
    return work


def test_verify_table_reports_each_kind(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    result = CliRunner().invoke(annotate_group, ["verify", "--root", str(work)])
    assert result.exit_code == 1, result.output
    assert "broken" in result.output.lower()
    assert "degraded" in result.output.lower()
    assert "fuzzy" in result.output.lower()
    assert "source.anno.trig" in result.output


def test_verify_clean_project_exits_zero(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "0 broken" in result.output or "all clean" in result.output.lower()


def test_verify_summary_only_suppresses_per_issue_lines(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    result = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(work), "--summary-only"]
    )
    assert result.exit_code == 1
    assert "a-broken" not in result.output
    assert "a-degraded" not in result.output
    assert "broken" in result.output.lower()


def test_verify_strict_promotes_degraded_and_fuzzy(tmp_path: Path) -> None:
    """In a fixture with no broken rows but degraded ones, --strict fails."""
    work = tmp_path / "project"
    work.mkdir()
    (work / "s.md").write_text("the bare phrase appears once here.\n")
    (work / "s.anno.trig").write_text(_one_degraded_sidecar())
    r1 = CliRunner().invoke(annotate_group, ["verify", "--root", str(work)])
    assert r1.exit_code == 0, r1.output
    r2 = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(work), "--strict"]
    )
    assert r2.exit_code == 1, r2.output


def test_verify_does_not_write_back_without_apply(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    before = (work / "source.anno.trig").read_text()
    CliRunner().invoke(annotate_group, ["verify", "--root", str(work)])
    after = (work / "source.anno.trig").read_text()
    assert before == after


def _one_degraded_sidecar() -> str:
    return (
        "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
        "@prefix oa:   <http://www.w3.org/ns/oa#> .\n"
        "@prefix dc:   <http://purl.org/dc/terms/> .\n"
        "@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .\n"
        "@prefix sci:  <http://example.org/science/vocab/> .\n"
        "@prefix anno: <#> .\n"
        "anno:annotations {\n"
        "  anno:a-d a oa:Annotation ;\n"
        "    oa:hasTarget [ oa:hasSource <s.md> ;\n"
        "      oa:hasSelector [ a oa:TextQuoteSelector ;\n"
        '        oa:exact "the bare phrase" ;\n'
        '        oa:prefix "PREFIX_THAT_DOES_NOT_MATCH " ;\n'
        '        oa:suffix " SUFFIX_THAT_DOES_NOT_MATCH" ] ] ;\n'
        '    oa:hasBody [ a oa:TextualBody ; dc:format "text/plain" ; rdf:value "x" ] ;\n'
        "    oa:motivatedBy oa:commenting ;\n"
        '    sci:annotationType "comment" ; sci:source "human:test" ;\n'
        '    sci:status "open" ; dc:creator "test" ;\n'
        '    dc:created "2026-05-11T00:00:00+00:00"^^xsd:dateTime .\n'
        "}\n"
    )
