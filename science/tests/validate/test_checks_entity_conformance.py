from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.entities import create_entity
from science_tool.validate.checks.entity_conformance import (
    check_entity_filename_conformance,
    check_entity_frontmatter_completeness,
    check_entity_location_coherence,
    check_entity_number_hygiene,
    check_entity_stray_files,
    check_overlay_of_in_owner_root,
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
    assert any(r.severity is Severity.ERROR and "doc/questions/0001-x.md" in str(r.path) for r in results)


def test_location_coherence_passes_for_correct_home(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "entities/questions/0001-x.md",
        {
            "id": "question:0001-x",
            "type": "question",
            "title": "X",
            "status": "active",
            "created": "2026-01-01",
            "updated": "2026-01-01",
        },
    )
    ctx = _ctx(tmp_path)
    assert not [r for r in check_entity_location_coherence(ctx) if r.severity is Severity.ERROR]


def test_location_coherence_flags_type_in_wrong_dir(tmp_path: Path) -> None:
    # a hypothesis-typed file living under entities/questions/
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "hypothesis:0001-x", "type": "hypothesis"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_location_coherence(ctx))
    assert any(r.severity is Severity.ERROR and "type" in r.message for r in results)


def test_filename_conformance_flags_legacy_name(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/q01-x.md", {"id": "question:q01-x", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_filename_conformance(ctx))
    assert any(r.severity is Severity.ERROR for r in results)


def test_filename_conformance_flags_stem_id_mismatch(tmp_path: Path) -> None:
    # well-formed name, but id local-part does not match the filename stem
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "question:0002-y", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_filename_conformance(ctx))
    assert any(r.severity is Severity.ERROR and "id" in r.message for r in results)


def test_filename_conformance_passes_for_padded(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "question:0001-x", "type": "question"})
    ctx = _ctx(tmp_path)
    assert not [r for r in check_entity_filename_conformance(ctx) if r.severity is Severity.ERROR]


def test_location_coherence_flags_id_kind_in_wrong_dir(tmp_path: Path) -> None:
    # correct type, but the id's kind prefix disagrees with the directory
    _write(tmp_path, "entities/questions/0001-x.md", {"id": "hypothesis:0001-x", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_location_coherence(ctx))
    assert any(r.severity is Severity.ERROR and "id kind" in r.message for r in results)


def test_frontmatter_completeness_flags_missing_fields(tmp_path: Path) -> None:
    # prose-header style: file with no frontmatter at all
    p = tmp_path / "entities" / "interpretations" / "0001-x.md"
    p.parent.mkdir(parents=True)
    p.write_text("**Date:** 2026-05-23\n\nbody\n", encoding="utf-8")
    ctx = _ctx(tmp_path)
    results = list(check_entity_frontmatter_completeness(ctx))
    assert any(r.severity is Severity.ERROR for r in results)


def test_number_hygiene_flags_duplicate(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/0001-a.md", {"id": "question:0001-a", "type": "question"})
    _write(tmp_path, "entities/questions/0001-b.md", {"id": "question:0001-b", "type": "question"})
    ctx = _ctx(tmp_path)
    results = list(check_entity_number_hygiene(ctx))
    assert any(r.severity is Severity.ERROR and "0001" in r.message for r in results)


def test_stray_file_flagged(tmp_path: Path) -> None:
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "questions" / "README.txt").write_text("notes", encoding="utf-8")
    ctx = _ctx(tmp_path)
    results = list(check_entity_stray_files(ctx))
    assert any(r.severity is Severity.ERROR for r in results)


def test_stray_subdirectory_flagged(tmp_path: Path) -> None:
    (tmp_path / "entities" / "questions" / "attachments").mkdir(parents=True)
    ctx = _ctx(tmp_path)
    results = list(check_entity_stray_files(ctx))
    assert any(r.severity is Severity.ERROR and "subdirectory" in r.message for r in results)


def test_number_hygiene_passes_for_distinct_numbers(tmp_path: Path) -> None:
    _write(tmp_path, "entities/questions/0001-a.md", {"id": "question:0001-a", "type": "question"})
    _write(tmp_path, "entities/questions/0002-b.md", {"id": "question:0002-b", "type": "question"})
    ctx = _ctx(tmp_path)
    assert not [r for r in check_entity_number_hygiene(ctx) if r.severity is Severity.ERROR]


@pytest.mark.parametrize("kind", ["finding", "synthesis", "hypothesis", "method", "paper", "inquiry"])
def test_freshly_created_entity_has_complete_required_frontmatter(tmp_path: Path, kind: str) -> None:
    # Regression: the real create code path (templates -> renderer) must emit
    # every _REQUIRED_FRONTMATTER field. finding/synthesis previously omitted
    # status/created/updated, so a freshly-created entity tripped the
    # completeness check. Exercise the real create path, not a synthetic fixture.
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 3\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    # paper uses a citekey id strategy and requires an explicit --id.
    entity_id = "paper:Smoke2026" if kind == "paper" else None
    create_entity(tmp_path, kind, f"Smoke {kind}", entity_id=entity_id)
    ctx = _ctx(tmp_path)
    missing = [r for r in check_entity_frontmatter_completeness(ctx) if "missing frontmatter fields" in r.message]
    assert not missing, [r.message for r in missing]


def test_stray_files_ignores_reservation_sentinel(tmp_path: Path) -> None:
    d = tmp_path / "entities" / "questions"
    d.mkdir(parents=True)
    (d / ".0001.reserving").write_text("", encoding="utf-8")
    (d / "0001-x.md").write_text("---\nid: question:0001-x\ntype: question\n---\n", encoding="utf-8")
    ctx = _ctx(tmp_path)
    results = list(check_entity_stray_files(ctx))
    assert not [r for r in results if r.severity is Severity.ERROR]


def test_overlay_of_in_owner_root_flagged_as_error_at_v3(tmp_path: Path) -> None:
    # an overlay file mistakenly placed under the owner root entities/
    _write(
        tmp_path,
        "entities/topics/0001-x.md",
        {"id": "topic:0001-x", "type": "topic", "overlay_of": "topic:0001-x"},
    )
    ctx = _ctx(tmp_path)  # _ctx writes layout_version: 3 -> ERROR
    results = list(check_overlay_of_in_owner_root(ctx))
    assert any(
        r.severity is Severity.ERROR and "overlay_of" in r.message and "entities/topics/0001-x.md" in str(r.path)
        for r in results
    )


def test_overlay_under_doc_is_flagged_at_v3(tmp_path: Path) -> None:
    # Post-2026-06-21: overlays live under overlays/<type>/, never in the prose-only
    # doc/ tree. An overlay_of file stranded in doc/<type>/ is a misplacement.
    _write(tmp_path, "doc/topics/bayesian.md", {"overlay_of": "topic:bayesian"})
    ctx = _ctx(tmp_path)  # _ctx writes layout_version: 3 -> ERROR
    results = list(check_overlay_of_in_owner_root(ctx))
    assert any(
        r.severity is Severity.ERROR and "overlay_of" in r.message and "doc/topics/bayesian.md" in str(r.path)
        for r in results
    )


def test_overlay_under_overlays_root_is_not_flagged(tmp_path: Path) -> None:
    # the legitimate location for an overlay; the check must ignore it
    _write(tmp_path, "overlays/topics/bayesian.md", {"overlay_of": "topic:bayesian"})
    ctx = _ctx(tmp_path)
    assert list(check_overlay_of_in_owner_root(ctx)) == []


def test_clean_owner_entity_is_not_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "entities/topics/0001-x.md",
        {
            "id": "topic:0001-x",
            "type": "topic",
            "title": "X",
            "status": "active",
            "created": "2026-01-01",
            "updated": "2026-01-01",
        },
    )
    ctx = _ctx(tmp_path)
    assert list(check_overlay_of_in_owner_root(ctx)) == []


def test_overlay_of_in_owner_root_warns_during_transition(tmp_path: Path) -> None:
    # layout_version 2 -> WARN, consistent with the sibling entity-conformance checks
    (tmp_path / "science.yaml").write_text(
        "name: t\nlayout_version: 2\nprofile: research\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    _write(
        tmp_path,
        "entities/topics/0001-x.md",
        {"id": "topic:0001-x", "type": "topic", "overlay_of": "topic:0001-x"},
    )
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    results = list(check_overlay_of_in_owner_root(ctx))
    assert results
    assert all(r.severity is Severity.WARN for r in results)


def test_overlay_of_under_entities_templates_is_ignored(tmp_path: Path) -> None:
    # template scaffolds under entities/**/templates/ are not entities and must be
    # skipped (mirrors the templates guard in check_entity_location_coherence)
    _write(
        tmp_path,
        "entities/questions/templates/example.md",
        {"id": "question:example", "type": "question", "overlay_of": "question:example"},
    )
    ctx = _ctx(tmp_path)
    assert list(check_overlay_of_in_owner_root(ctx)) == []


def test_overlay_of_check_registered_via_canonical_loader() -> None:
    import sys

    from science_tool.validate.checks import (
        CANONICAL_CHECKS,
        _load_canonical_checks,
        clear_checks_for_tests,
    )

    original_entries = list(CANONICAL_CHECKS)  # snapshot process-global registry
    module_name = "science_tool.validate.checks.entity_conformance"
    original_module = sys.modules.get(module_name)
    try:
        clear_checks_for_tests()
        # Drop the cached module so _load_canonical_checks() must re-import it
        # from the CANONICAL_CHECK_MODULES tuple. If entity_conformance were ever
        # dropped from that tuple, the module's @Check decorators would not re-run
        # and this assertion would fail — that is what makes this a true wiring test.
        sys.modules.pop(module_name, None)
        _load_canonical_checks()
        entries = [e for e in CANONICAL_CHECKS if e.fn.__name__ == "check_overlay_of_in_owner_root"]
        assert len(entries) == 1
        assert entries[0].order == 42
    finally:
        CANONICAL_CHECKS[:] = original_entries  # restore for later in-process tests
        if original_module is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = original_module
