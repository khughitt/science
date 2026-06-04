from __future__ import annotations

from collections.abc import Iterable
import importlib
from pathlib import Path

from science_tool.validate import Result, Severity, ValidateContext
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


def _ctx(root: Path) -> ValidateContext:
    _write_manifest(root)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _messages(results: Iterable[Result]) -> list[str]:
    return [result.message for result in results]


def test_registration_includes_papers_and_gap_analysis_before_research_plan() -> None:
    clear_checks_for_tests()

    import science_tool.validate.checks.gap_analysis as gap_analysis
    import science_tool.validate.checks.hypotheses as hypotheses
    import science_tool.validate.checks.papers as papers
    import science_tool.validate.checks.research_plan as research_plan

    importlib.reload(hypotheses)
    importlib.reload(papers)
    importlib.reload(gap_analysis)
    importlib.reload(research_plan)

    assert [(entry.section, entry.order) for entry in CANONICAL_CHECKS[-4:]] == [
        ("hypotheses...", 5),
        ("paper summaries...", 7),
        ("research gap analysis...", 9),
        ("research plan conventions...", 10),
    ]


def test_papers_check_emits_info_message(tmp_path: Path) -> None:
    from science_tool.validate.checks.papers import check_papers

    results = list(check_papers(_ctx(tmp_path)))

    assert [(result.severity, result.message) for result in results] == [
        (Severity.INFO, "Paper summary structure is checked in entities/papers/")
    ]


def test_gap_analysis_no_files_emits_info_message(tmp_path: Path) -> None:
    from science_tool.validate.checks.gap_analysis import check_gap_analysis

    results = list(check_gap_analysis(_ctx(tmp_path)))

    assert [(result.severity, result.message) for result in results] == [
        (Severity.INFO, "No next-steps analysis found (doc/meta/next-steps-*.md)")
    ]


def test_gap_analysis_warns_for_each_missing_required_section(tmp_path: Path) -> None:
    from science_tool.validate.checks.gap_analysis import check_gap_analysis

    meta_dir = tmp_path / "doc" / "meta"
    meta_dir.mkdir(parents=True)
    meta_dir.joinpath("next-steps-2026-01-02.md").write_text("# Plan\n", encoding="utf-8")

    results = list(check_gap_analysis(_ctx(tmp_path)))

    assert _messages(results) == [
        "Next-steps doc/meta/next-steps-2026-01-02.md missing section: Recent Progress",
        "Next-steps doc/meta/next-steps-2026-01-02.md missing section: Current State",
        "Next-steps doc/meta/next-steps-2026-01-02.md missing section: Coverage Gaps",
        "Next-steps doc/meta/next-steps-2026-01-02.md missing section: Recommended Next Actions",
    ]
    assert [result.severity for result in results] == [Severity.WARN] * 4


def test_gap_analysis_meta_prior_resolves_existing_file_without_warning(tmp_path: Path) -> None:
    from science_tool.validate.checks.gap_analysis import check_gap_analysis

    meta_dir = tmp_path / "doc" / "meta"
    meta_dir.mkdir(parents=True)
    meta_dir.joinpath("next-steps-2026-01-01.md").write_text("# Previous\n", encoding="utf-8")
    meta_dir.joinpath("next-steps-2026-01-02.md").write_text(
        "\n".join(
            [
                "prior: meta:next-steps-2026-01-01",
                "## Recent Progress",
                "## Current State",
                "## Coverage Gaps",
                "## Recommended Next Actions",
            ]
        ),
        encoding="utf-8",
    )

    results = list(check_gap_analysis(_ctx(tmp_path)))

    assert not any("broken prior link" in result.message for result in results)


def test_gap_analysis_broken_prior_warns_with_resolved_path(tmp_path: Path) -> None:
    from science_tool.validate.checks.gap_analysis import check_gap_analysis

    meta_dir = tmp_path / "doc" / "meta"
    meta_dir.mkdir(parents=True)
    meta_dir.joinpath("next-steps-2026-01-02.md").write_text(
        "\n".join(
            [
                'prior: "meta:next-steps-2026-01-01"',
                "## Recent Progress",
                "## Current State",
                "## Coverage Gaps",
                "## Recommended Next Actions",
            ]
        ),
        encoding="utf-8",
    )

    results = list(check_gap_analysis(_ctx(tmp_path)))

    assert _messages(results) == [
        "doc/meta/next-steps-2026-01-02.md: broken prior link 'meta:next-steps-2026-01-01' "
        "(resolved to doc/meta/next-steps-2026-01-01.md)"
    ]


def test_gap_analysis_relative_md_prior_resolves_from_project_root(tmp_path: Path) -> None:
    from science_tool.validate.checks.gap_analysis import check_gap_analysis

    meta_dir = tmp_path / "doc" / "meta"
    meta_dir.mkdir(parents=True)
    meta_dir.joinpath("prior.md").write_text("# Previous\n", encoding="utf-8")
    meta_dir.joinpath("next-steps-2026-01-02.md").write_text(
        "\n".join(
            [
                "prior: doc/meta/prior.md",
                "## Recent Progress",
                "## Current State",
                "## Coverage Gaps",
                "## Recommended Next Actions",
            ]
        ),
        encoding="utf-8",
    )

    results = list(check_gap_analysis(_ctx(tmp_path)))

    assert not any("broken prior link" in result.message for result in results)
