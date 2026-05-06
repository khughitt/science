"""Tests for per-entry ref validation in science_tool.dag.refs."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from science_tool.dag.refs import RefResolutionError, validate_ref_entry
from science_tool.dag.schema import RefEntry


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    # Simulate research-profile project layout.
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks/active.md").write_text("## [t001] Example\n## [t002] Another\n")
    (tmp_path / "tasks/done").mkdir()
    (tmp_path / "tasks/done/2026-04.md").write_text("## [t204] Done task\n- completed: 2026-04-18\n")
    (tmp_path / "doc/interpretations").mkdir(parents=True)
    (tmp_path / "doc/interpretations/2026-04-18-t204-verdict.md").write_text("ok")
    (tmp_path / "doc/discussions").mkdir()
    (tmp_path / "doc/discussions/2026-04-19-dag-iteration.md").write_text("ok")
    (tmp_path / "specs/propositions").mkdir(parents=True)
    (tmp_path / "specs/propositions/p11-rival-state.md").write_text("ok")
    (tmp_path / "doc/papers").mkdir()
    (tmp_path / "doc/papers/Ren2019.md").write_text("ok")
    return tmp_path


def test_task_resolves(project_root: Path) -> None:
    entry = RefEntry.model_validate({"task": "t001", "description": "cites active task"})
    validate_ref_entry(entry, project_root)  # no exception


def test_done_task_resolves(project_root: Path) -> None:
    entry = RefEntry.model_validate({"task": "t204", "description": "cites completed task"})
    validate_ref_entry(entry, project_root)


def test_unresolved_task_raises(project_root: Path) -> None:
    entry = RefEntry.model_validate({"task": "t99999", "description": "nonexistent"})
    with pytest.raises(RefResolutionError, match="task t99999 not found"):
        validate_ref_entry(entry, project_root)


def test_interpretation_resolves(project_root: Path) -> None:
    entry = RefEntry.model_validate({"interpretation": "2026-04-18-t204-verdict", "description": ""})
    validate_ref_entry(entry, project_root)


def test_unresolved_interpretation_raises(project_root: Path) -> None:
    entry = RefEntry.model_validate({"interpretation": "2026-04-18-does-not-exist", "description": ""})
    with pytest.raises(RefResolutionError, match="interpretation .* not found"):
        validate_ref_entry(entry, project_root)


def test_discussion_resolves(project_root: Path) -> None:
    entry = RefEntry.model_validate({"discussion": "2026-04-19-dag-iteration", "description": ""})
    validate_ref_entry(entry, project_root)


def test_proposition_resolves(project_root: Path) -> None:
    entry = RefEntry.model_validate({"proposition": "p11-rival-state", "description": ""})
    validate_ref_entry(entry, project_root)


def test_paper_resolves(project_root: Path) -> None:
    entry = RefEntry.model_validate({"paper": "Ren2019", "description": ""})
    validate_ref_entry(entry, project_root)


def test_unresolved_paper_raises(project_root: Path) -> None:
    entry = RefEntry.model_validate({"paper": "Nonexistent2099", "description": ""})
    with pytest.raises(RefResolutionError, match="paper .* not found"):
        validate_ref_entry(entry, project_root)


def test_doi_warns_when_paper_missing(project_root: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    entry = RefEntry.model_validate({"doi": "10.1234/nonexistent", "description": ""})
    validate_ref_entry(entry, project_root)  # no exception
    assert any("doi" in rec.message.lower() for rec in caplog.records)


def test_doi_invalid_syntax_raises(project_root: Path) -> None:
    entry = RefEntry.model_validate({"doi": "not-a-doi", "description": ""})
    with pytest.raises(RefResolutionError, match="invalid DOI"):
        validate_ref_entry(entry, project_root)


def test_accession_geo_format_accepted(project_root: Path) -> None:
    entry = RefEntry.model_validate({"accession": "GSE136410", "description": ""})
    validate_ref_entry(entry, project_root)  # regex-valid


def test_accession_unknown_format_warns(project_root: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    entry = RefEntry.model_validate({"accession": "not-a-known-format-12345", "description": ""})
    validate_ref_entry(entry, project_root)  # warn-only
    assert any("accession" in rec.message.lower() for rec in caplog.records)
