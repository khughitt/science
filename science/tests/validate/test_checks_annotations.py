from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

from science_tool.validate import Severity, ValidateContext
from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests


@dataclass(frozen=True)
class FakeReport:
    sidecars: int = 0
    annotations: int = 0
    broken: int = 0
    degraded: int = 0
    fuzzy: int = 0
    source_missing: int = 0
    parse_errors: int = 0
    superseded_skipped: int = 0
    issues: tuple[object, ...] = ()


@dataclass(frozen=True)
class FakeIssue:
    sidecar: Path
    annotation_id: str
    source: str
    kind: str
    exact_preview: str


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


def _summary(results) -> list[tuple[Severity, str, str | None]]:
    return [(result.severity, result.message, result.rule) for result in results]


def _located_summary(results) -> list[tuple[Severity, Path | None, str, str | None]]:
    return [(result.severity, result.path, result.message, result.rule) for result in results]


def test_no_sidecars_emits_exact_info_message(tmp_path: Path) -> None:
    from science_tool.validate.checks.annotations import check_annotations

    results = list(check_annotations(_ctx(tmp_path)))

    assert _summary(results) == [(Severity.INFO, "no annotation sidecars (*.anno.trig) in this project", "annotations")]


def test_broken_and_parse_errors_emit_warn_messages(tmp_path: Path, monkeypatch) -> None:
    import science_tool.validate.checks.annotations as annotations_check

    sidecar = tmp_path / "doc" / "note.anno.trig"
    monkeypatch.setattr(
        annotations_check,
        "verify_path",
        lambda root: FakeReport(
            sidecars=2,
            annotations=5,
            broken=1,
            parse_errors=1,
            issues=(
                FakeIssue(sidecar, "a-1", "note.md", "broken", "missing\nquote"),
                FakeIssue(tmp_path / "bad.anno.trig", "", "", "parse-error", "bad syntax"),
            ),
        ),
    )

    results = list(annotations_check.check_annotations(_ctx(tmp_path)))

    assert _located_summary(results) == [
        (
            Severity.WARN,
            Path("doc/note.anno.trig"),
            "annotation a-1 broken selector in note.md; preview: missing quote",
            "annotations.broken",
        ),
        (Severity.WARN, Path("bad.anno.trig"), "sidecar parse error: bad syntax", "annotations.parse-error"),
    ]


def test_non_strict_suppresses_strict_annotation_warnings(tmp_path: Path, monkeypatch) -> None:
    import science_tool.validate.checks.annotations as annotations_check

    monkeypatch.setattr(
        annotations_check,
        "verify_path",
        lambda root: FakeReport(sidecars=1, annotations=3, degraded=1, fuzzy=1, source_missing=1),
    )

    results = list(annotations_check.check_annotations(_ctx(tmp_path)))

    assert results == []


def test_strict_emits_degraded_fuzzy_and_source_missing_warns(tmp_path: Path, monkeypatch) -> None:
    import science_tool.validate.checks.annotations as annotations_check

    sidecar = tmp_path / "doc" / "note.anno.trig"
    monkeypatch.setattr(
        annotations_check,
        "verify_path",
        lambda root: FakeReport(
            sidecars=1,
            annotations=3,
            degraded=1,
            fuzzy=1,
            source_missing=1,
            issues=(
                FakeIssue(sidecar, "a-1", "note.md", "degraded", "old quote"),
                FakeIssue(sidecar, "a-2", "note.md", "fuzzy", "near quote"),
                FakeIssue(sidecar, "a-3", "missing.md", "source-missing", "missing source quote"),
            ),
        ),
    )

    results = list(annotations_check.check_annotations(_ctx(tmp_path, strict=True)))

    assert _located_summary(results) == [
        (
            Severity.WARN,
            Path("doc/note.anno.trig"),
            "annotation a-1 degraded selector in note.md; preview: old quote",
            "annotations.degraded",
        ),
        (
            Severity.WARN,
            Path("doc/note.anno.trig"),
            "annotation a-2 fuzzy selector in note.md; preview: near quote",
            "annotations.fuzzy",
        ),
        (
            Severity.WARN,
            Path("doc/note.anno.trig"),
            "annotation a-3 source missing: missing.md; preview: missing source quote",
            "annotations.source-missing",
        ),
    ]


def test_clean_sidecars_emit_exact_info_message(tmp_path: Path, monkeypatch) -> None:
    import science_tool.validate.checks.annotations as annotations_check

    monkeypatch.setattr(
        annotations_check,
        "verify_path",
        lambda root: FakeReport(sidecars=2, annotations=7),
    )

    results = list(annotations_check.check_annotations(_ctx(tmp_path)))

    assert _summary(results) == [
        (Severity.INFO, "7 annotation(s) across 2 sidecar(s); all selectors clean", "annotations")
    ]


def test_registration_includes_annotations_after_prose_lints() -> None:
    import science_tool.validate.checks.annotations as annotations_check
    import science_tool.validate.checks.prose_lints as prose_lints

    original_entries = list(CANONICAL_CHECKS)
    try:
        clear_checks_for_tests()
        importlib.reload(prose_lints)
        importlib.reload(annotations_check)

        ordered = [(entry.section, entry.order, entry.fn.__module__) for entry in CANONICAL_CHECKS]

        prose_lints_index = next(index for index, entry in enumerate(ordered) if entry[0] == "prose quality lints...")
        annotations_index = next(index for index, entry in enumerate(ordered) if entry[0] == "annotation drift...")

        assert annotations_index == prose_lints_index + 1
        assert ordered[annotations_index] == (
            "annotation drift...",
            22,
            "science_tool.validate.checks.annotations",
        )
    finally:
        CANONICAL_CHECKS[:] = original_entries
