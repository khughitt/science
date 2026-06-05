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

    _write(tmp_path / "entities" / "reports" / "a.md", "---\ntype: report\nid: report:a\n---\n")

    results = list(check_id_prefixes(_ctx(tmp_path)))

    assert _messages(results) == ["  all type/id prefixes conform"]
    assert [result.severity for result in results] == [Severity.INFO]


def test_mismatched_report_id_under_entities_warns_exactly(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    _write(tmp_path / "entities" / "reports" / "a.md", "---\ntype: report\nid: doc:a\n---\n")

    results = list(check_id_prefixes(_ctx(tmp_path)))

    assert _messages(results, Severity.WARN) == [
        "id-prefix mismatch: entities/reports/a.md: type=report but id=doc:a (expected prefix 'report:')"
    ]


def test_scans_entities_in_deterministic_order(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    _write(tmp_path / "entities" / "reports" / "z.md", "---\ntype: report\nid: doc:z\n---\n")
    _write(tmp_path / "entities" / "questions" / "a.md", "---\ntype: question\nid: doc:a\n---\n")

    assert _messages(check_id_prefixes(_ctx(tmp_path)), Severity.WARN) == [
        "id-prefix mismatch: entities/questions/a.md: type=question but id=doc:a (expected prefix 'question:')",
        "id-prefix mismatch: entities/reports/z.md: type=report but id=doc:z (expected prefix 'report:')",
    ]


def test_skips_templates_path(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    _write(tmp_path / "entities" / "templates" / "a.md", "---\ntype: report\nid: doc:a\n---\n")
    _write(tmp_path / "entities" / "nested" / "templates" / "b.md", "---\ntype: report\nid: doc:b\n---\n")

    assert _messages(check_id_prefixes(_ctx(tmp_path))) == ["  all type/id prefixes conform"]


def test_templates_ancestor_outside_project_does_not_skip_project_files(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    project_root = tmp_path / "templates" / "project"
    _write(project_root / "entities" / "reports" / "a.md", "---\ntype: report\nid: doc:a\n---\n")

    assert _messages(check_id_prefixes(_ctx(project_root)), Severity.WARN) == [
        "id-prefix mismatch: entities/reports/a.md: type=report but id=doc:a (expected prefix 'report:')"
    ]


def test_ignores_missing_frontmatter_missing_fields_and_unknown_type(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    _write(tmp_path / "entities" / "reports" / "body.md", "type: report\nid: doc:a\n")
    _write(tmp_path / "entities" / "reports" / "missing-type.md", "---\nid: doc:a\n---\n")
    _write(tmp_path / "entities" / "reports" / "missing-id.md", "---\ntype: report\n---\n")
    _write(tmp_path / "entities" / "reports" / "unknown.md", "---\ntype: custom\nid: doc:a\n---\n")

    assert _messages(check_id_prefixes(_ctx(tmp_path))) == ["  all type/id prefixes conform"]


def test_handles_quoted_type_and_id_like_bash_regex(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    _write(tmp_path / "entities" / "reports" / "a.md", "---\ntype: 'report'\nid: \"doc:a\"\n---\n")

    assert _messages(check_id_prefixes(_ctx(tmp_path)), Severity.WARN) == [
        "id-prefix mismatch: entities/reports/a.md: type=report but id=doc:a (expected prefix 'report:')"
    ]


def test_skip_environment_emits_no_results(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    monkeypatch.setenv("SCIENCE_VALIDATE_SKIP_ID_PREFIX", "1")
    _write(tmp_path / "entities" / "reports" / "a.md", "---\ntype: report\nid: doc:a\n---\n")

    assert list(check_id_prefixes(_ctx(tmp_path))) == []


def test_read_encoding_errors_propagate(tmp_path: Path) -> None:
    from science_tool.validate.checks.id_prefixes import check_id_prefixes

    path = tmp_path / "entities" / "reports" / "bad.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"---\ntype: report\nid: report:\xff\n---\n")

    with pytest.raises(UnicodeDecodeError):
        list(check_id_prefixes(_ctx(tmp_path)))


def test_prefix_rules_cover_every_markdown_kind() -> None:
    from science_tool.entities import markdown_entity_kinds
    from science_tool.validate.checks.id_prefixes import prefix_rules

    rules = prefix_rules()
    for kind in markdown_entity_kinds():
        if kind in {"research-question", "claim-registry"}:
            continue  # singletons validated elsewhere
        assert rules.get(kind) == f"{kind}:", f"{kind} missing/incorrect prefix rule"


def test_prefix_rules_retain_nonpolicy_kinds() -> None:
    # Regression guard: deriving rules from the policy table must NOT drop
    # non-policy kinds the static PREFIX_RULES used to cover. `concept` and
    # `dataset` are not markdown entity kinds (absent from the policy table)
    # but still carry typed `concept:`/`dataset:` ids that need conformance.
    from science_tool.validate.checks.id_prefixes import prefix_rules

    rules = prefix_rules()
    for kind in ("concept", "dataset", "spec"):
        assert rules.get(kind) == f"{kind}:", f"{kind} prefix rule was dropped"


def test_id_prefixes_scans_entities_dir(tmp_path) -> None:
    # a type/id mismatch under entities/ must be detected
    (tmp_path / "science.yaml").write_text("name: t\nlayout_version: 3\n", encoding="utf-8")
    d = tmp_path / "entities" / "questions"
    d.mkdir(parents=True)
    (d / "0001-x.md").write_text('---\ntype: question\nid: "hypothesis:0001-x"\n---\n', encoding="utf-8")
    from science_tool.validate.context import ValidateContext
    from science_tool.validate.checks.id_prefixes import check_id_prefixes
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    assert any(r.severity is Severity.WARN for r in check_id_prefixes(ctx))


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
