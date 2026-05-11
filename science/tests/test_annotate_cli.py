"""CLI tests for `science annotate verify`."""

from __future__ import annotations

import json
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


def test_verify_json_schema_summary_keys(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    result = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(work), "--format", "json"]
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert set(payload.keys()) == {"summary", "issues"}
    summary = payload["summary"]
    assert set(summary.keys()) == {
        "sidecars",
        "annotations",
        "broken",
        "degraded",
        "fuzzy",
        "source_missing",
        "parse_errors",
        "superseded_skipped",
    }
    assert summary["broken"] >= 1
    assert summary["degraded"] >= 1
    assert summary["fuzzy"] >= 1


def test_verify_json_issues_use_relative_sidecar_paths(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    result = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(work), "--format", "json"]
    )
    payload = json.loads(result.output)
    for issue in payload["issues"]:
        assert not issue["sidecar"].startswith("/")
        assert "annotation_id" in issue
        assert "source" in issue
        assert "kind" in issue
        assert issue["kind"] in (
            "broken",
            "degraded",
            "fuzzy",
            "source-missing",
            "parse-error",
        )


def test_verify_json_summary_only_omits_issues_array(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    result = CliRunner().invoke(
        annotate_group,
        ["verify", "--root", str(work), "--format", "json", "--summary-only"],
    )
    payload = json.loads(result.output)
    assert "issues" not in payload
    assert "summary" in payload


def test_verify_json_clean_project(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["broken"] == 0
    assert payload["summary"]["sidecars"] == 0
    assert payload["issues"] == []


import subprocess


def _git_init(work: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    subprocess.run(["git", "add", "."], cwd=work, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=work,
        check=True,
    )


def test_verify_apply_requires_actor(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    _git_init(work)
    result = CliRunner().invoke(
        annotate_group, ["verify", "--root", str(work), "--apply"]
    )
    assert result.exit_code != 0
    assert "actor" in result.output.lower()


def test_verify_apply_writes_back_supersessions(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    _git_init(work)
    result = CliRunner().invoke(
        annotate_group,
        [
            "verify",
            "--root",
            str(work),
            "--apply",
            "--actor",
            "ci@science",
        ],
    )
    assert result.exit_code == 0, result.output
    follow = CliRunner().invoke(annotate_group, ["verify", "--root", str(work)])
    assert "0 broken" in follow.output
    text = (work / "source.anno.trig").read_text()
    assert "ci@science" in text
    assert '"superseded"' in text


def test_verify_apply_refuses_dirty_anno_files(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    _git_init(work)
    (work / "source.anno.trig").write_text(
        (work / "source.anno.trig").read_text() + "\n# dirty\n"
    )
    result = CliRunner().invoke(
        annotate_group,
        [
            "verify",
            "--root",
            str(work),
            "--apply",
            "--actor",
            "ci@science",
        ],
    )
    assert result.exit_code != 0
    assert "dirty" in result.output.lower() or "uncommitted" in result.output.lower()


def test_verify_apply_force_dirty_overrides_guard(tmp_path: Path) -> None:
    work = _seed(tmp_path)
    _git_init(work)
    (work / "source.anno.trig").write_text(
        (work / "source.anno.trig").read_text() + "\n# dirty\n"
    )
    result = CliRunner().invoke(
        annotate_group,
        [
            "verify",
            "--root",
            str(work),
            "--apply",
            "--actor",
            "ci@science",
            "--force-dirty",
        ],
    )
    assert "dirty" not in result.output.lower()


def test_verify_apply_zero_broken_is_noop(tmp_path: Path) -> None:
    """When there's nothing broken, --apply still exits 0 and writes nothing."""
    result = CliRunner().invoke(
        annotate_group,
        [
            "verify",
            "--root",
            str(tmp_path),
            "--apply",
            "--actor",
            "ci@science",
        ],
    )
    assert result.exit_code == 0


def test_verify_apply_json_emits_pure_json_with_apply_block(tmp_path: Path) -> None:
    """--apply --format json must emit valid JSON only, no human prose mixed in."""
    work = _seed(tmp_path)
    _git_init(work)
    result = CliRunner().invoke(
        annotate_group,
        [
            "verify",
            "--root",
            str(work),
            "--apply",
            "--actor",
            "ci@science",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "apply" in payload
    assert payload["apply"]["rewritten_sidecars"] >= 1
    assert payload["apply"]["superseded_annotations"] >= 1
    assert payload["summary"]["broken"] == 0


def test_verify_apply_exits_nonzero_when_parse_errors_present(tmp_path: Path) -> None:
    """Parse errors are not fixable by --apply, so they remain hard failures."""
    work = tmp_path / "project"
    work.mkdir()
    (work / "broken.anno.trig").write_text("not valid trig {{{")
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    subprocess.run(["git", "add", "."], cwd=work, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=work,
        check=True,
    )
    result = CliRunner().invoke(
        annotate_group,
        [
            "verify",
            "--root",
            str(work),
            "--apply",
            "--actor",
            "ci@science",
        ],
    )
    assert result.exit_code == 1, result.output


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
