"""Tests for science_tool.commons.validator."""
from __future__ import annotations

import shutil
from pathlib import Path

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.validator import CommonsValidator, ValidationReport

FIXTURES = Path(__file__).parent / "fixtures" / "commons"


def _make_store(tmp_path: Path, subdir: str) -> Path:
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / subdir, root)
    return root


def test_validate_clean_store_reports_no_errors(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    report = CommonsValidator(CommonsEntityAdapter(root)).validate()
    assert isinstance(report, ValidationReport)
    assert report.errors == []
    assert report.checked == 5


def test_validate_collects_per_entity_errors(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    # Drop in an invalid paper. The bibkey "bad-name" (with a hyphen) violates
    # the paper-mixin bibkey regex, so schema validation fails — while the
    # filename/id/type stay mutually consistent so the failure is purely the
    # schema check.
    bad = root / "papers" / "badname.md"
    bad.write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:badname"\n'
        'type: "paper"\n'
        'title: "Bad"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "bad-name"\n'
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    report = CommonsValidator(CommonsEntityAdapter(root)).validate()
    assert report.checked == 6
    assert len(report.errors) == 1
    assert report.errors[0].path == bad


def test_validate_filters_by_type(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    report = CommonsValidator(CommonsEntityAdapter(root)).validate(type="paper")
    assert report.checked == 1
    assert report.errors == []


def test_validate_filters_by_slug(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    report = CommonsValidator(CommonsEntityAdapter(root)).validate(slug="Adams2025")
    assert report.checked == 1
    assert report.errors == []


def test_validate_type_filter_excludes_error_of_other_type(tmp_path: Path) -> None:
    """An error from a paper must not appear (or be counted) when validating
    only datasets."""
    root = _make_store(tmp_path, "valid")
    bad = root / "papers" / "badname.md"
    bad.write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:badname"\n'
        'type: "paper"\n'
        'title: "Bad"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "bad-name"\n'
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    report = CommonsValidator(CommonsEntityAdapter(root)).validate(type="dataset")
    assert report.errors == []
    assert report.checked == 2  # the two valid datasets only
