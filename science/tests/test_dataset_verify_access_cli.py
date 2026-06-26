"""Tests for `science dataset verify-access`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _legacy(tmp_path: Path, slug: str = "foo", **overrides) -> Path:
    fm = {
        "id": f"dataset:{slug}",
        "type": "dataset",
        "title": slug.title(),
        "status": "candidate",
        "source_class": "observational",
        "created": "2026-01-01",
        "updated": "2026-01-01",
    }
    fm.update(overrides)
    dest = tmp_path / "entities" / "datasets" / f"{slug}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
    dest.write_text(f"---\n{front}---\n\n# {slug}\n\nlegacy.\n", encoding="utf-8")
    return dest


def _run(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["dataset", "verify-access", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )


def test_cli_verify_access_backfills_and_reports_readiness(tmp_path: Path) -> None:
    _legacy(tmp_path)
    res = _run(tmp_path, "foo", "--level", "public", "--method", "retrieved",
               "--license", "CC0-1.0", "--note", "public landing page")
    assert res.exit_code == 0, res.output
    text = (tmp_path / "entities" / "datasets" / "foo.md").read_text(encoding="utf-8")
    assert "origin: external" in text
    assert "verified: true" in text
    assert "available" in res.output
    assert "weight 1" in res.output
    assert "runtime=unstaged-deposit" in res.output


def test_cli_verify_access_accepts_dataset_class(tmp_path: Path) -> None:
    _legacy(tmp_path, license="MIT")

    res = _run(
        tmp_path,
        "foo",
        "--class",
        "reference",
        "--level",
        "public",
        "--method",
        "landing-confirmed",
        "--source-url",
        "https://example.org/foo",
    )

    assert res.exit_code == 0, res.output
    text = (tmp_path / "entities" / "datasets" / "foo.md").read_text(encoding="utf-8")
    assert "dataset_class: reference" in text
    assert "runtime=reference-only" in res.output


def test_cli_verify_access_missing_method_errors(tmp_path: Path) -> None:
    _legacy(tmp_path)
    res = _run(tmp_path, "foo", "--level", "public", "--license", "CC0-1.0")
    assert res.exit_code == 1
    assert "--method" in res.output


@pytest.mark.parametrize("method", ["landing-confirmed", "metadata-confirmed"])
def test_cli_verify_access_accepts_reference_verification_methods(tmp_path: Path, method: str) -> None:
    _legacy(tmp_path)

    res = _run(
        tmp_path,
        "foo",
        "--class",
        "reference",
        "--level",
        "public",
        "--method",
        method,
        "--license",
        "CC0-1.0",
        "--source-url",
        "https://example.org/foo",
    )

    assert res.exit_code == 0, res.output
    text = (tmp_path / "entities" / "datasets" / "foo.md").read_text(encoding="utf-8")
    assert f"verification_method: {method}" in text


@pytest.mark.parametrize("extra", [("--method", "retrieved"), ("--exception", "scope-reduced")])
def test_cli_verify_access_missing_license_errors(tmp_path: Path, extra: tuple[str, ...]) -> None:
    _legacy(tmp_path)
    res = _run(tmp_path, "foo", *extra)
    assert res.exit_code == 1
    assert "--license" in res.output


def test_cli_verify_access_exception_path(tmp_path: Path) -> None:
    _legacy(tmp_path)
    res = _run(tmp_path, "foo", "--exception", "scope-reduced", "--license", "unknown",
               "--rationale", "defer", "--followup-task", "task:t1")
    assert res.exit_code == 0, res.output
    assert "consumable-via-scope-reduced" in res.output


def test_cli_verify_access_refuses_derived(tmp_path: Path) -> None:
    _legacy(
        tmp_path, "der",
        origin="derived", source_class="derived", derived_kind="aggregate",
        derivation={"kind": "member_of", "parent_dataset": "dataset:p", "member_key": "k"},
    )
    res = _run(tmp_path, "der", "--method", "retrieved", "--license", "CC0-1.0")
    assert res.exit_code == 1
    assert "register-run" in res.output
