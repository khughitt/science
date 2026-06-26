"""Tests for `science dataset add`."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _add(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["dataset", "add", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )


def test_add_creates_candidate_entity(tmp_path: Path) -> None:
    res = _add(tmp_path, "my-set", "--title", "My Set", "--source-url", "https://example.org")
    assert res.exit_code == 0, res.output
    p = tmp_path / "entities" / "datasets" / "my-set.md"
    assert p.exists()
    text = p.read_text(encoding="utf-8")
    assert "dataset:my-set" in text
    assert "status: candidate" in text
    assert "origin: external" in text
    assert "dataset_class: deposit" in text
    assert "license: unknown" in text
    assert "verified: false" in text


def test_add_accepts_reference_class_with_source_url(tmp_path: Path) -> None:
    res = _add(
        tmp_path,
        "portal",
        "--title",
        "Portal",
        "--class",
        "reference",
        "--source-url",
        "https://example.org/portal",
    )

    assert res.exit_code == 0, res.output
    text = (tmp_path / "entities" / "datasets" / "portal.md").read_text(encoding="utf-8")
    assert "dataset_class: reference" in text
    assert "source_url: https://example.org/portal" in text


def test_add_reference_requires_source_url(tmp_path: Path) -> None:
    res = _add(tmp_path, "portal", "--title", "Portal", "--class", "reference")

    assert res.exit_code == 1
    assert "--source-url" in res.output


def test_add_rejects_derived(tmp_path: Path) -> None:
    res = _add(tmp_path, "x", "--title", "X", "--origin", "derived")
    assert res.exit_code == 1
    assert "register-run" in res.output


def test_add_rejects_existing_destination(tmp_path: Path) -> None:
    _add(tmp_path, "dup", "--title", "Dup")
    res = _add(tmp_path, "dup", "--title", "Dup again")
    assert res.exit_code == 1
    assert "already exists" in res.output


def test_add_rejects_bad_slug(tmp_path: Path) -> None:
    res = _add(tmp_path, "Bad_Slug", "--title", "Bad")
    assert res.exit_code == 1
    assert "slug" in res.output.lower()


def test_add_with_commons_related_ref_does_not_crash(tmp_path: Path) -> None:
    # A commons-looking related ref must not crash author-time even when no
    # commons store is reachable: add does a local-only prospective validation.
    res = CliRunner().invoke(
        science_cli,
        ["dataset", "add", "linked", "--title", "Linked", "--related", "cycles:paper:Aras2025"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )
    assert res.exit_code == 0, res.output
    assert (tmp_path / "entities" / "datasets" / "linked.md").exists()
