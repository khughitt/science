from __future__ import annotations

import importlib
from collections.abc import Iterable
from pathlib import Path

import pytest

from science_tool.validate import Result, Severity, ValidateContext
from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests


def _write_manifest(root: Path, *, local_profile: str = "demo") -> None:
    root.mkdir(parents=True, exist_ok=True)
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "id: demo-project",
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                "profile: research",
                "layout_version: 1",
                "knowledge_profiles:",
                f"  local: {local_profile}",
                "peers:",
                "  - id: peer-project",
            ]
        ),
        encoding="utf-8",
    )


def _ctx(root: Path, *, local_profile: str = "demo") -> ValidateContext:
    _write_manifest(root, local_profile=local_profile)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _messages(results: Iterable[Result], severity: Severity | None = None) -> list[str]:
    return [result.message for result in results if severity is None or result.severity is severity]


def test_passing_local_related_refs_emit_exact_info(tmp_path: Path) -> None:
    from science_tool.validate.checks.cross_references import check_cross_references

    _write(tmp_path / "entities" / "questions" / "0001-a.md", "---\nid: question:a\nrelated: [report:b]\n---\n")
    _write(tmp_path / "entities" / "reports" / "0001-b.md", "---\nid: report:b\n---\n")

    results = list(check_cross_references(_ctx(tmp_path)))

    assert _messages(results) == ["All frontmatter cross-references valid"]
    assert [result.severity for result in results] == [Severity.INFO]


def test_broken_related_ref_warns_with_basename_only(tmp_path: Path) -> None:
    from science_tool.validate.checks.cross_references import check_cross_references

    _write(tmp_path / "entities" / "reports" / "a.md", "---\nid: report:a\nrelated: [missing:ref]\n---\n")

    results = list(check_cross_references(_ctx(tmp_path)))

    assert _messages(results, Severity.WARN) == ["Broken reference in a.md: related ID 'missing:ref' not found"]


def test_inline_and_block_related_parsing_ignores_templates(tmp_path: Path) -> None:
    from science_tool.validate.checks.cross_references import check_cross_references

    _write(tmp_path / "entities" / "questions" / "a.md", "---\nid: question:a\nrelated: ['report:b', \"topic:c\"]\n---\n")
    _write(
        tmp_path / "entities" / "reports" / "b.md",
        "---\nid: report:b\nrelated:\n  - topic:c\n  - '{{ template }}'\nother: value\n---\n",
    )
    _write(tmp_path / "entities" / "topics" / "c.md", "---\nid: topic:c\n---\n")

    assert _messages(check_cross_references(_ctx(tmp_path))) == ["All frontmatter cross-references valid"]


def test_task_ids_resolve_refs_but_retired_aggregate_ids_do_not(tmp_path: Path) -> None:
    from science_tool.validate.checks.cross_references import check_cross_references

    _write(
        tmp_path / "entities" / "reports" / "a.md",
        "---\nid: report:a\nrelated: [task:t001, task:t099, entity:one, term:one]\n---\n",
    )
    _write(tmp_path / "tasks" / "active.md", "## [t001] Active task\n")
    _write(tmp_path / "tasks" / "done" / "archive.md", "## [T099] Done task\n")
    _write(tmp_path / "knowledge" / "sources" / "demo" / "entities.yaml", "entities:\n  - canonical_id: entity:one\n")
    _write(tmp_path / "knowledge" / "sources" / "demo" / "terms.yaml", "terms:\n  - id: term:one\n")

    assert _messages(check_cross_references(_ctx(tmp_path)), Severity.WARN) == [
        "Broken reference in a.md: related ID 'entity:one' not found",
        "Broken reference in a.md: related ID 'term:one' not found",
    ]


def test_unknown_namespace_errors_and_known_cross_project_ref_is_ignored(tmp_path: Path) -> None:
    from science_tool.validate.checks.cross_references import check_cross_references

    _write(
        tmp_path / "entities" / "reports" / "a.md",
        "---\nid: report:a\nrelated: [unknown:question:x, peer-project:question:y]\n---\n",
    )

    results = list(check_cross_references(_ctx(tmp_path)))

    assert _messages(results, Severity.ERROR) == [
        "Unknown project namespace 'unknown' in ref 'unknown:question:x'. "
        "Add it to science.yaml peers: or use a local ref."
    ]
    assert _messages(results, Severity.WARN) == []


def test_known_two_part_legacy_project_ref_warns_without_all_valid_info(tmp_path: Path) -> None:
    from science_tool.validate.checks.cross_references import check_cross_references

    _write(tmp_path / "entities" / "reports" / "a.md", "---\nid: report:a\nrelated: [peer-project:slug]\n---\n")

    results = list(check_cross_references(_ctx(tmp_path)))

    assert _messages(results) == [
        "Legacy cross-project ref 'peer-project:slug' is missing an entity kind. "
        "Use 'peer-project:question:slug' or another explicit <project-id>:<kind>:<slug> ref."
    ]
    assert [result.severity for result in results] == [Severity.WARN]


def test_unknown_two_part_non_local_kind_ref_remains_local_and_can_be_broken(tmp_path: Path) -> None:
    from science_tool.validate.checks.cross_references import check_cross_references

    _write(tmp_path / "entities" / "reports" / "a.md", "---\nid: report:a\nrelated: [customkind:slug]\n---\n")

    assert _messages(check_cross_references(_ctx(tmp_path)), Severity.WARN) == [
        "Broken reference in a.md: related ID 'customkind:slug' not found"
    ]


def test_loader_registry_includes_cross_references_after_id_prefixes_at_order_20() -> None:
    import science_tool.validate.checks.cross_references as cross_references
    import science_tool.validate.checks.id_prefixes as id_prefixes

    original_entries = list(CANONICAL_CHECKS)
    try:
        clear_checks_for_tests()
        importlib.reload(id_prefixes)
        importlib.reload(cross_references)

        ordered = [(entry.section, entry.order, entry.fn.__module__) for entry in CANONICAL_CHECKS]

        id_prefixes_index = next(
            index for index, entry in enumerate(ordered) if entry[0] == "per-kind id-prefix conformance..."
        )
        cross_references_index = next(
            index for index, entry in enumerate(ordered) if entry[0] == "frontmatter cross-references..."
        )

        assert cross_references_index == id_prefixes_index + 1
        assert ordered[cross_references_index] == (
            "frontmatter cross-references...",
            20,
            "science_tool.validate.checks.cross_references",
        )
    finally:
        CANONICAL_CHECKS[:] = original_entries


def test_read_encoding_errors_on_scanned_markdown_propagate(tmp_path: Path) -> None:
    from science_tool.validate.checks.cross_references import check_cross_references

    path = tmp_path / "entities" / "reports" / "bad.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"---\nid: report:\xff\n---\n")

    with pytest.raises(UnicodeDecodeError):
        list(check_cross_references(_ctx(tmp_path)))


# ---------------------------------------------------------------------------
# Task 8: dual-root — entities/**/*.md ids join the known-id set
# ---------------------------------------------------------------------------

def test_entities_dir_id_resolves_cross_references(tmp_path: Path) -> None:
    """An id defined in entities/questions/0001-x.md is known; a ref to it is NOT broken."""
    from science_tool.validate.checks.cross_references import check_cross_references

    _write(tmp_path / "entities" / "questions" / "0001-x.md", "---\nid: question:0001-x\n---\n")
    _write(tmp_path / "doc" / "a.md", "---\nid: report:a\nrelated: [question:0001-x]\n---\n")

    results = list(check_cross_references(_ctx(tmp_path)))

    messages = [r.message for r in results]
    assert not any("question:0001-x" in m and "not found" in m for m in messages), messages
    assert _messages(results) == ["All frontmatter cross-references valid"]
