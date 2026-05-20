from __future__ import annotations

from collections.abc import Iterable
import importlib
from pathlib import Path

import pytest

from science_tool.validate import Result, Severity, ValidateContext
from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests


def _write_manifest(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                "profile: research",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: knowledge/local",
            ]
        ),
        encoding="utf-8",
    )


def _ctx(root: Path) -> ValidateContext:
    _write_manifest(root)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _messages(results: Iterable[Result], severity: Severity | None = None) -> list[str]:
    return [result.message for result in results if severity is None or result.severity is severity]


def test_matching_prefixes_emit_info(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    _write(tmp_path / "doc" / "reports" / "a.md", "---\ntype: report\nid: report:a\n---\n")

    results = list(check_id_prefixes(_ctx(tmp_path)))

    assert _messages(results) == ["  all type/id prefixes conform"]
    assert [result.severity for result in results] == [Severity.INFO]


def test_mismatched_report_id_under_doc_warns_exactly(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    _write(tmp_path / "doc" / "reports" / "a.md", "---\ntype: report\nid: doc:a\n---\n")

    results = list(check_id_prefixes(_ctx(tmp_path)))

    assert _messages(results, Severity.WARN) == [
        "id-prefix mismatch: doc/reports/a.md: type=report but id=doc:a (expected prefix 'report:')"
    ]


def test_scans_doc_and_specs_in_deterministic_order(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    _write(tmp_path / "doc" / "z.md", "---\ntype: report\nid: doc:z\n---\n")
    _write(tmp_path / "doc" / "a.md", "---\ntype: question\nid: doc:a\n---\n")
    _write(tmp_path / "specs" / "b.md", "---\ntype: spec\nid: report:b\n---\n")

    assert _messages(check_id_prefixes(_ctx(tmp_path)), Severity.WARN) == [
        "id-prefix mismatch: doc/a.md: type=question but id=doc:a (expected prefix 'question:')",
        "id-prefix mismatch: doc/z.md: type=report but id=doc:z (expected prefix 'report:')",
        "id-prefix mismatch: specs/b.md: type=spec but id=report:b (expected prefix 'spec:')",
    ]


def test_skips_templates_path(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    _write(tmp_path / "doc" / "templates" / "a.md", "---\ntype: report\nid: doc:a\n---\n")
    _write(tmp_path / "specs" / "nested" / "templates" / "b.md", "---\ntype: spec\nid: report:b\n---\n")

    assert _messages(check_id_prefixes(_ctx(tmp_path))) == ["  all type/id prefixes conform"]


def test_templates_ancestor_outside_project_does_not_skip_project_files(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    project_root = tmp_path / "templates" / "project"
    _write(project_root / "doc" / "reports" / "a.md", "---\ntype: report\nid: doc:a\n---\n")

    assert _messages(check_id_prefixes(_ctx(project_root)), Severity.WARN) == [
        "id-prefix mismatch: doc/reports/a.md: type=report but id=doc:a (expected prefix 'report:')"
    ]


def test_ignores_missing_frontmatter_missing_fields_and_unknown_type(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    _write(tmp_path / "doc" / "body.md", "type: report\nid: doc:a\n")
    _write(tmp_path / "doc" / "missing-type.md", "---\nid: doc:a\n---\n")
    _write(tmp_path / "doc" / "missing-id.md", "---\ntype: report\n---\n")
    _write(tmp_path / "doc" / "unknown.md", "---\ntype: custom\nid: doc:a\n---\n")

    assert _messages(check_id_prefixes(_ctx(tmp_path))) == ["  all type/id prefixes conform"]


def test_handles_quoted_type_and_id_like_bash_regex(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    _write(tmp_path / "doc" / "a.md", "---\ntype: 'report'\nid: \"doc:a\"\n---\n")

    assert _messages(check_id_prefixes(_ctx(tmp_path)), Severity.WARN) == [
        "id-prefix mismatch: doc/a.md: type=report but id=doc:a (expected prefix 'report:')"
    ]


def test_skip_environment_emits_no_results(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    monkeypatch.setenv("SCIENCE_VALIDATE_SKIP_ID_PREFIX", "1")
    _write(tmp_path / "doc" / "a.md", "---\ntype: report\nid: doc:a\n---\n")

    assert list(check_id_prefixes(_ctx(tmp_path))) == []


def test_read_encoding_errors_propagate(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    path = tmp_path / "doc" / "bad.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"---\ntype: report\nid: report:\xff\n---\n")

    with pytest.raises(UnicodeDecodeError):
        list(check_id_prefixes(_ctx(tmp_path)))


def test_loader_registry_includes_id_prefixes_after_tasks_at_order_19() -> None:
    import science_tool.validate.checks.id_prefixes as id_prefixes
    import science_tool.validate.checks.tasks as tasks

    original_entries = list(CANONICAL_CHECKS)
    try:
        clear_checks_for_tests()
        importlib.reload(tasks)
        importlib.reload(id_prefixes)

        ordered = [(entry.section, entry.order, entry.fn.__module__) for entry in CANONICAL_CHECKS]

        tasks_index = next(index for index, entry in enumerate(ordered) if entry[0] == "task queue...")
        id_prefixes_index = next(
            index for index, entry in enumerate(ordered) if entry[0] == "per-type id-prefix conformance..."
        )

        assert id_prefixes_index == tasks_index + 1
        assert ordered[id_prefixes_index] == (
            "per-type id-prefix conformance...",
            19,
            "science_tool.validate.checks.id_prefixes",
        )
    finally:
        CANONICAL_CHECKS[:] = original_entries
