from __future__ import annotations

import importlib
from collections.abc import Iterable
from pathlib import Path

from science_tool.validate import Result, Severity, ValidateContext
from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests


def _write_manifest(root: Path, *, prose_lint: str = "") -> None:
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
                "  local: knowledge/local",
                prose_lint.rstrip(),
            ]
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _ctx(
    root: Path,
    *,
    strict: bool = False,
    prose_lint: str = "",
    include_all_checks: bool = False,
) -> ValidateContext:
    _write_manifest(root, prose_lint=prose_lint)
    return ValidateContext.from_project_root(
        root,
        strict=strict,
        verbose=False,
        include_all_checks=include_all_checks,
    )


def _write_doc(root: Path, text: str) -> None:
    path = root / "doc" / "note.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _summary(results: Iterable[Result]) -> list[tuple[Severity, str, str | None]]:
    return [(result.severity, result.message, result.rule) for result in results]


def _located_summary(results: Iterable[Result]) -> list[tuple[Severity, Path | None, int | None, str, str | None]]:
    return [(result.severity, result.path, result.line, result.message, result.rule) for result in results]


def test_missing_doc_directory_emits_no_results(tmp_path: Path) -> None:
    from science_tool.validate.checks.prose_lints import check_prose_lints

    results = list(check_prose_lints(_ctx(tmp_path)))

    assert results == []


def test_non_strict_bare_author_year_emits_exact_warn_message(tmp_path: Path) -> None:
    from science_tool.validate.checks.prose_lints import check_prose_lints

    _write_doc(tmp_path, "Smith 2020 argues that the result is robust.\n")

    results = list(check_prose_lints(_ctx(tmp_path)))

    assert _located_summary(results) == [
        (
            Severity.WARN,
            Path("doc/note.md"),
            1,
            "bare author-year mention 'Smith 2020' has no adjacent [@key]",
            "prose_lints.bare-author-year",
        )
    ]


def test_non_strict_numeric_anchor_is_silent(tmp_path: Path) -> None:
    from science_tool.validate.checks.prose_lints import check_prose_lints

    _write_doc(tmp_path, "The cohort included 123 participants without a linked anchor.\n")

    results = list(check_prose_lints(_ctx(tmp_path)))

    assert _summary(results) == [
        (Severity.INFO, "1 prose lint issue(s): numeric-anchor (use --strict to promote)", "prose_lints.numeric-anchor")
    ]


def test_strict_numeric_anchor_emits_warn_message(tmp_path: Path) -> None:
    from science_tool.validate.checks.prose_lints import check_prose_lints

    _write_doc(tmp_path, "The cohort included 123 participants without a linked anchor.\n")

    results = list(check_prose_lints(_ctx(tmp_path, strict=True)))

    assert _located_summary(results) == [
        (
            Severity.WARN,
            Path("doc/note.md"),
            1,
            "numeric claim '123' has no anchor in this paragraph",
            "prose_lints.numeric-anchor",
        )
    ]


def test_project_config_controls_enabled_checks_and_anchor_patterns(tmp_path: Path) -> None:
    from science_tool.validate.checks.prose_lints import check_prose_lints

    _write_doc(
        tmp_path,
        "\n".join(
            [
                "Smith 2020 should be ignored because only numeric anchors are enabled.",
                "",
                "The cohort included 123 participants, anchored by custom-anchor.",
            ]
        ),
    )

    results = list(
        check_prose_lints(
            _ctx(
                tmp_path,
                prose_lint="\n".join(
                    [
                        "prose_lint:",
                        "  enabled_checks:",
                        "    - numeric-anchor",
                        "  anchor_patterns:",
                        "    - custom-anchor",
                    ]
                ),
            )
        )
    )

    assert _summary(results) == [
        (
            Severity.INFO,
            "prose lint checks limited by science.yaml: 1/5 enabled (numeric-anchor); disabled: bare-author-year, short-form-ids, frontmatter-inline-gap, unsupported-citation-syntax",
            "prose_lints.config",
        )
    ]


def test_include_all_checks_overrides_project_enabled_checks(tmp_path: Path) -> None:
    from science_tool.validate.checks.prose_lints import check_prose_lints

    _write_doc(
        tmp_path,
        "\n".join(
            [
                "Smith 2020 should be reported when all checks are active.",
                "",
                "The cohort included 123 participants, anchored by custom-anchor.",
            ]
        ),
    )

    results = list(
        check_prose_lints(
            _ctx(
                tmp_path,
                include_all_checks=True,
                prose_lint="\n".join(
                    [
                        "prose_lint:",
                        "  enabled_checks:",
                        "    - numeric-anchor",
                        "  anchor_patterns:",
                        "    - custom-anchor",
                    ]
                ),
            )
        )
    )

    assert _summary(results)[:1] == [
        (
            Severity.INFO,
            "prose lint checks limited by science.yaml but --all is active; running all 5 checks (science.yaml enabled: numeric-anchor)",
            "prose_lints.config",
        )
    ]
    assert (
        Severity.WARN,
        Path("doc/note.md"),
        1,
        "bare author-year mention 'Smith 2020' has no adjacent [@key]",
        "prose_lints.bare-author-year",
    ) in _located_summary(results)


def test_strict_include_all_checks_promotes_disabled_info_lints(tmp_path: Path) -> None:
    from science_tool.validate.checks.prose_lints import check_prose_lints

    _write_doc(tmp_path, "The cohort included 123 participants without a linked anchor.\n")

    results = list(
        check_prose_lints(
            _ctx(
                tmp_path,
                strict=True,
                include_all_checks=True,
                prose_lint="\n".join(
                    [
                        "prose_lint:",
                        "  enabled_checks:",
                        "    - unsupported-citation-syntax",
                    ]
                ),
            )
        )
    )

    assert (
        Severity.WARN,
        Path("doc/note.md"),
        1,
        "numeric claim '123' has no anchor in this paragraph",
        "prose_lints.numeric-anchor",
    ) in _located_summary(results)


def test_strict_frontmatter_inline_gap_stays_summary_only(tmp_path: Path) -> None:
    from science_tool.validate.checks.prose_lints import check_prose_lints

    path = tmp_path / "doc" / "note.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "related:\n"
        "  - task:t001\n"
        "  - hypothesis:h001\n"
        "---\n"
        "Body text without graph metadata mentions.\n",
        encoding="utf-8",
    )

    results = list(check_prose_lints(_ctx(tmp_path, strict=True)))

    assert _summary(results) == [
        (
            Severity.INFO,
            "2 prose lint issue(s): frontmatter-inline-gap (graph metadata advisory)",
            "prose_lints.frontmatter-inline-gap",
        )
    ]


def test_registration_includes_prose_lints_after_cross_references() -> None:
    import science_tool.validate.checks.cross_references as cross_references
    import science_tool.validate.checks.prose_lints as prose_lints

    original_entries = list(CANONICAL_CHECKS)
    try:
        clear_checks_for_tests()
        importlib.reload(cross_references)
        importlib.reload(prose_lints)

        ordered = [(entry.section, entry.order, entry.fn.__module__) for entry in CANONICAL_CHECKS]

        cross_references_index = next(
            index for index, entry in enumerate(ordered) if entry[0] == "frontmatter cross-references..."
        )
        prose_lints_index = next(index for index, entry in enumerate(ordered) if entry[0] == "prose quality lints...")

        # cross_references.py also registers the archive-index reconciliation check
        # (a sibling in the same module, order=21); it sorts between cross-references
        # and prose lints. prose lints must still follow the cross-references section.
        assert prose_lints_index > cross_references_index
        archive_index = next(
            index for index, entry in enumerate(ordered) if entry[0] == "archive index reconciliation"
        )
        assert cross_references_index < archive_index < prose_lints_index
        assert ordered[prose_lints_index] == (
            "prose quality lints...",
            21,
            "science_tool.validate.checks.prose_lints",
        )
    finally:
        CANONICAL_CHECKS[:] = original_entries
