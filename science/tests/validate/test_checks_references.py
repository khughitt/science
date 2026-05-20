from __future__ import annotations

import importlib
from pathlib import Path

from science_tool.refs import RefIssue
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


def _ctx(root: Path) -> ValidateContext:
    _write_manifest(root)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _issue(ref_type: str) -> RefIssue:
    return RefIssue(
        file="doc/example.md",
        line=1,
        ref_type=ref_type,
        ref_value="missing",
        message="missing reference",
    )


def test_no_broken_refs_emits_exact_info_and_no_warns(tmp_path: Path, monkeypatch) -> None:
    from science_tool.validate.checks import references

    monkeypatch.setattr(references, "check_refs", lambda root: [_issue("marker")])

    results = list(references.check_references(_ctx(tmp_path)))

    assert [(result.severity, result.message, result.rule) for result in results] == [
        (Severity.INFO, "Reference integrity check complete (no broken refs)", "references")
    ]
    assert not any(result.severity is Severity.WARN for result in results)


def test_broken_refs_are_grouped_by_type_and_sorted(tmp_path: Path, monkeypatch) -> None:
    from science_tool.validate.checks import references

    monkeypatch.setattr(
        references,
        "check_refs",
        lambda root: [
            _issue("link"),
            _issue("citation"),
            _issue("link"),
            _issue("marker"),
        ],
    )

    results = list(references.check_references(_ctx(tmp_path)))

    assert [(result.severity, result.message, result.rule) for result in results] == [
        (Severity.WARN, "1 broken refs: citation", "references"),
        (Severity.WARN, "2 broken refs: link", "references"),
    ]


def test_marker_only_issues_are_ignored(tmp_path: Path, monkeypatch) -> None:
    from science_tool.validate.checks import references

    monkeypatch.setattr(references, "check_refs", lambda root: [_issue("marker"), _issue("marker")])

    results = list(references.check_references(_ctx(tmp_path)))

    assert [(result.severity, result.message) for result in results] == [
        (Severity.INFO, "Reference integrity check complete (no broken refs)")
    ]


def test_registration_includes_references_between_hypotheses_and_papers() -> None:
    clear_checks_for_tests()

    import science_tool.validate.checks.hypotheses as hypotheses
    import science_tool.validate.checks.papers as papers
    import science_tool.validate.checks.references as references

    importlib.reload(hypotheses)
    importlib.reload(references)
    importlib.reload(papers)

    assert [(entry.section, entry.order) for entry in CANONICAL_CHECKS[-3:]] == [
        ("hypotheses...", 5),
        ("reference integrity...", 7),
        ("paper summaries...", 7),
    ]
