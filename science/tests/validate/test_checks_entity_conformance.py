from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.validate.checks.entity_conformance import (
    check_entity_filename_conformance,
    check_entity_frontmatter_completeness,
    check_entity_location_coherence,
    check_entity_number_hygiene,
    check_entity_stray_files,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _ctx(tmp_path: Path) -> ValidateContext:
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    return ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)


def _write(root: Path, rel: str, fm: dict) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\n" + yaml.safe_dump(fm) + "---\n", encoding="utf-8")


def test_location_coherence_flags_stranded_entity(tmp_path: Path) -> None:
    _write(tmp_path, "doc/questions/0001-x.md", {"id": "question:0001-x", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_location_coherence(ctx))
    assert any(r.severity is Severity.WARN and "doc/questions/0001-x.md" in str(r.path) for r in results)


def test_location_coherence_passes_for_correct_home(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "question:0001-x", "type": "question", "title": "X", "status": "active", "created": "2026-01-01", "updated": "2026-01-01"})
    ctx = _ctx(tmp_path)
    assert not [r for r in check_entity_location_coherence(ctx) if r.severity is Severity.WARN]


def test_location_coherence_flags_type_in_wrong_dir(tmp_path: Path) -> None:
    # a hypothesis-typed file living under entities/questions/
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "hypothesis:0001-x", "type": "hypothesis"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_location_coherence(ctx))
    assert any(r.severity is Severity.WARN and "type" in r.message for r in results)


def test_filename_conformance_flags_legacy_name(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/q01-x.md", {"id": "question:q01-x", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_filename_conformance(ctx))
    assert any(r.severity is Severity.WARN for r in results)


def test_filename_conformance_flags_stem_id_mismatch(tmp_path: Path) -> None:
    # well-formed name, but id local-part does not match the filename stem
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "question:0002-y", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_filename_conformance(ctx))
    assert any(r.severity is Severity.WARN and "id" in r.message for r in results)


def test_filename_conformance_passes_for_padded(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "question:0001-x", "type": "question"})
    ctx = _ctx(tmp_path)
    assert not [r for r in check_entity_filename_conformance(ctx) if r.severity is Severity.WARN]


def test_location_coherence_flags_id_kind_in_wrong_dir(tmp_path: Path) -> None:
    # correct type, but the id's kind prefix disagrees with the directory
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "hypothesis:0001-x", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_location_coherence(ctx))
    assert any(r.severity is Severity.WARN and "id kind" in r.message for r in results)


def test_frontmatter_completeness_flags_missing_fields(tmp_path: Path) -> None:
    # prose-header style: file with no frontmatter at all
    p = tmp_path / "entities" / "interpretations" / "0001-x.md"
    p.parent.mkdir(parents=True)
    p.write_text("**Date:** 2026-05-23\n\nbody\n", encoding="utf-8")
    ctx = _ctx(tmp_path)
    results = list(check_entity_frontmatter_completeness(ctx))
    assert any(r.severity is Severity.WARN for r in results)


def test_number_hygiene_flags_duplicate(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/0001-a.md", {"id": "question:0001-a", "type": "question"})
    _write(tmp_path, "entities/questions/0001-b.md", {"id": "question:0001-b", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_number_hygiene(ctx))
    assert any(r.severity is Severity.WARN and "0001" in r.message for r in results)


def test_stray_file_flagged(tmp_path: Path) -> None:
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "questions" / "README.txt").write_text("notes", encoding="utf-8")
    ctx = _ctx(tmp_path)
    results = list(check_entity_stray_files(ctx))
    assert any(r.severity is Severity.WARN for r in results)


def test_stray_subdirectory_flagged(tmp_path: Path) -> None:
    (tmp_path / "entities" / "questions" / "attachments").mkdir(parents=True)
    ctx = _ctx(tmp_path)
    results = list(check_entity_stray_files(ctx))
    assert any(r.severity is Severity.WARN and "subdirectory" in r.message for r in results)


def test_number_hygiene_passes_for_distinct_numbers(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/0001-a.md", {"id": "question:0001-a", "type": "question"})
    _write(tmp_path, "entities/questions/0002-b.md", {"id": "question:0002-b", "type": "question"})
    ctx = _ctx(tmp_path)
    assert not [r for r in check_entity_number_hygiene(ctx) if r.severity is Severity.WARN]
