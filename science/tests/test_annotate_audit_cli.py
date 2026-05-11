"""CLI: science annotate audit."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.annotation.cli import annotate_group

FX = Path(__file__).parent / "_fixtures" / "annotation" / "audit"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    doc = tmp_path / "doc"
    doc.mkdir()
    for name in ("bare-author-year.md", "short-form-ids.md", "numeric-anchor.md"):
        shutil.copy(FX / name, doc / name)
    return tmp_path


def test_audit_default_runs_lint_sources(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        ["audit", "--root", str(workspace), "--actor", "tester"],
    )
    assert result.exit_code == 0
    assert any(
        (workspace / "doc" / f"{stem}.anno.trig").exists()
        for stem in ("bare-author-year", "short-form-ids", "numeric-anchor")
    )


def test_audit_source_filter(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--source", "bare-author-year",
            "--actor", "tester",
        ],
    )
    assert result.exit_code == 0
    assert (workspace / "doc" / "bare-author-year.anno.trig").exists()
    assert not (workspace / "doc" / "numeric-anchor.anno.trig").exists()


def test_audit_unknown_source_rejected(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--source", "made-up-source", "--actor", "tester",
        ],
    )
    assert result.exit_code == 1
    assert "made-up-source" in (result.output + (str(result.exception) or ""))


def test_audit_marker_token_accepted_as_source(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--source", "marker-token", "--actor", "tester",
        ],
    )
    assert result.exit_code == 0


def test_audit_frontmatter_inline_gap_rejected(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--source", "frontmatter-inline-gap", "--actor", "tester",
        ],
    )
    assert result.exit_code == 1


def test_audit_dry_run_writes_no_files(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--dry-run", "--actor", "tester",
        ],
    )
    assert result.exit_code == 0
    for stem in ("bare-author-year", "short-form-ids", "numeric-anchor"):
        assert not (workspace / "doc" / f"{stem}.anno.trig").exists()


def test_audit_format_json_shape(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--format", "json", "--actor", "tester",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "summary" in payload
    assert "files" in payload
    assert payload["summary"]["files_scanned"] >= 3
    assert isinstance(payload["summary"]["sources_run"], list)
    assert any(
        s.startswith("lint:bare-author-year-")
        for s in payload["summary"]["sources_run"]
    )


def test_audit_records_actor_as_creator(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--source", "bare-author-year",
            "--actor", "operator-alpha",
        ],
    )
    assert result.exit_code == 0
    sidecar = (workspace / "doc" / "bare-author-year.anno.trig").read_text()
    assert "operator-alpha" in sidecar


def test_audit_no_llm_flag_accepted(workspace: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        annotate_group,
        [
            "audit", "--root", str(workspace),
            "--no-llm", "--actor", "tester",
        ],
    )
    assert result.exit_code == 0


def test_audit_rerun_writes_zero_new_rows(workspace: Path) -> None:
    runner = CliRunner()
    args = [
        "audit", "--root", str(workspace),
        "--source", "bare-author-year",
        "--format", "json", "--actor", "tester",
    ]
    runner.invoke(annotate_group, args)
    second = runner.invoke(annotate_group, args)
    assert second.exit_code == 0
    payload = json.loads(second.output)
    assert payload["summary"]["rows_written"] == 0
