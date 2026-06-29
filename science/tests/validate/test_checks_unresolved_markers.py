from __future__ import annotations

import importlib
from pathlib import Path

from science_tool.validate import Severity, ValidateContext
from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests


def _write_manifest(root: Path) -> None:
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


def _ctx(root: Path, *, strict: bool = False) -> ValidateContext:
    _write_manifest(root)
    return ValidateContext.from_project_root(root, strict=strict, verbose=False)


def test_missing_doc_directory_emits_no_results(tmp_path: Path) -> None:
    from science_tool.validate.checks.unresolved_markers import check_unresolved_markers

    results = list(check_unresolved_markers(_ctx(tmp_path)))

    assert results == []


def test_warning_token_in_doc_markdown_emits_exact_warn_message(tmp_path: Path) -> None:
    from science_tool.validate.checks.unresolved_markers import check_unresolved_markers

    doc_dir = tmp_path / "doc"
    doc_dir.mkdir()
    doc_dir.joinpath("note.md").write_text("This needs work. [UNVERIFIED]\n", encoding="utf-8")

    results = list(check_unresolved_markers(_ctx(tmp_path)))

    assert [(result.severity, result.path, result.line, result.message, result.rule) for result in results] == [
        (
            Severity.WARN,
            None,
            None,
            "1 [UNVERIFIED] marker(s) found in documents; examples: doc/note.md:1",
            "unresolved_markers",
        )
    ]


def test_info_token_in_non_strict_mode_emits_no_result(tmp_path: Path) -> None:
    from science_tool.validate.checks.unresolved_markers import check_unresolved_markers

    doc_dir = tmp_path / "doc"
    doc_dir.mkdir()
    doc_dir.joinpath("note.md").write_text("Maybe this is true. [SPECULATION]\n", encoding="utf-8")

    results = list(check_unresolved_markers(_ctx(tmp_path)))

    assert results == []


def test_info_token_in_strict_mode_emits_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.unresolved_markers import check_unresolved_markers

    doc_dir = tmp_path / "doc"
    doc_dir.mkdir()
    doc_dir.joinpath("note.md").write_text("Maybe this is true. [SPECULATION]\n", encoding="utf-8")

    results = list(check_unresolved_markers(_ctx(tmp_path, strict=True)))

    assert [(result.severity, result.message) for result in results] == [
        (Severity.WARN, "1 [SPECULATION] marker(s) found in documents; examples: doc/note.md:1")
    ]


def test_documentation_backticked_and_fenced_markers_are_ignored_by_default(tmp_path: Path) -> None:
    from science_tool.validate.checks.unresolved_markers import check_unresolved_markers

    doc_dir = tmp_path / "doc"
    doc_dir.mkdir()
    doc_dir.joinpath("conventions.md").write_text(
        "\n".join(
            [
                "Mention `[UNVERIFIED]` inline.",
                "",
                "```",
                "[MISSING_CITATION]",
                "```",
            ]
        ),
        encoding="utf-8",
    )

    results = list(check_unresolved_markers(_ctx(tmp_path)))

    assert results == []


def test_warn_tokens_are_output_sorted_alphabetically(tmp_path: Path) -> None:
    from science_tool.validate.checks.unresolved_markers import check_unresolved_markers

    doc_dir = tmp_path / "doc"
    doc_dir.mkdir()
    doc_dir.joinpath("note.md").write_text(
        "\n".join(
            [
                "[UNVERIFIED]",
                "[MISSING_CITATION]",
                "[UNVERIFIED]",
            ]
        ),
        encoding="utf-8",
    )

    results = list(check_unresolved_markers(_ctx(tmp_path)))

    assert [result.message for result in results] == [
        "1 [MISSING_CITATION] marker(s) found in documents; examples: doc/note.md:2",
        "2 [UNVERIFIED] marker(s) found in documents; examples: doc/note.md:1, doc/note.md:3",
    ]


def test_warning_marker_examples_are_capped(tmp_path: Path) -> None:
    from science_tool.validate.checks.unresolved_markers import check_unresolved_markers

    doc_dir = tmp_path / "doc"
    doc_dir.mkdir()
    doc_dir.joinpath("note.md").write_text("\n".join(["[UNVERIFIED]"] * 7) + "\n", encoding="utf-8")

    results = list(check_unresolved_markers(_ctx(tmp_path)))

    assert [result.message for result in results] == [
        "7 [UNVERIFIED] marker(s) found in documents; examples: "
        "doc/note.md:1, doc/note.md:2, doc/note.md:3, doc/note.md:4, doc/note.md:5, ..."
    ]


def test_registration_includes_unresolved_markers_between_papers_and_gap_analysis() -> None:
    clear_checks_for_tests()

    import science_tool.validate.checks.gap_analysis as gap_analysis
    import science_tool.validate.checks.papers as papers
    import science_tool.validate.checks.unresolved_markers as unresolved_markers

    importlib.reload(papers)
    importlib.reload(unresolved_markers)
    importlib.reload(gap_analysis)

    assert [(entry.section, entry.order) for entry in CANONICAL_CHECKS[-3:]] == [
        ("paper summaries...", 7),
        ("for unresolved markers...", 8),
        ("research gap analysis...", 9),
    ]


def test_lifted_filter_can_drop_all_hits(tmp_path: Path, monkeypatch) -> None:
    from science_tool.validate.checks import unresolved_markers

    doc_dir = tmp_path / "doc"
    doc_dir.mkdir()
    doc_dir.joinpath("note.md").write_text("[UNVERIFIED]\n", encoding="utf-8")
    monkeypatch.setattr(unresolved_markers, "_filter_lifted", lambda hits: [])

    results = list(unresolved_markers.check_unresolved_markers(_ctx(tmp_path)))

    assert results == []
