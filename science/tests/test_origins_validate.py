"""Tests for the origin-reference validation check.

Behavior-level: build a small project on disk, invoke ``check_origin_refs``
directly, and assert findings. Mirrors the invocation pattern used by
``tests/validate/test_checks_cross_references.py``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from science_tool.validate import Result, Severity, ValidateContext
from science_tool.validate.checks.origins import check_origin_refs


def _write_manifest(root: Path) -> None:
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


def test_unknown_cite_key_origin_warns(tmp_path: Path) -> None:
    _write(
        tmp_path / "entities" / "questions" / "0001-a.md",
        "---\nid: question:a\norigins:\n  - type: literature\n    ref: cite:Ghost2020\n---\nBody.\n",
    )

    results = list(check_origin_refs(_ctx(tmp_path)))

    warns = _messages(results, Severity.WARN)
    assert any("Ghost2020" in message for message in warns), warns


def test_known_cite_key_origin_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path / "papers" / "references.bib",
        "@article{Known2020,\n  title = {A known paper},\n  year = {2020},\n}\n",
    )
    _write(
        tmp_path / "entities" / "questions" / "0001-a.md",
        "---\nid: question:a\norigins:\n  - type: literature\n    ref: cite:Known2020\n---\nBody.\n",
    )

    results = list(check_origin_refs(_ctx(tmp_path)))

    assert not any("Known2020" in message for message in _messages(results)), _messages(results)


def test_unresolved_paper_origin_warns(tmp_path: Path) -> None:
    _write(
        tmp_path / "entities" / "questions" / "0001-a.md",
        "---\nid: question:a\norigins:\n  - type: literature\n    ref: paper:missing-key\n---\nBody.\n",
    )

    results = list(check_origin_refs(_ctx(tmp_path)))

    warns = _messages(results, Severity.WARN)
    assert any("paper:missing-key" in message for message in warns), warns


def test_resolved_paper_origin_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path / "entities" / "papers" / "smith2020.md",
        "---\nid: paper:smith2020\n---\nA paper.\n",
    )
    _write(
        tmp_path / "entities" / "questions" / "0001-a.md",
        "---\nid: question:a\norigins:\n  - type: literature\n    ref: paper:smith2020\n---\nBody.\n",
    )

    results = list(check_origin_refs(_ctx(tmp_path)))

    assert not any("smith2020" in message for message in _messages(results)), _messages(results)


def test_lone_independent_origin_warns(tmp_path: Path) -> None:
    _write(
        tmp_path / "entities" / "questions" / "0001-a.md",
        "---\nid: question:a\norigins:\n  - type: user\n    independent: true\n---\nBody.\n",
    )

    results = list(check_origin_refs(_ctx(tmp_path)))

    warns = _messages(results, Severity.WARN)
    assert any("independent" in message.lower() for message in warns), warns


def test_two_independent_origins_do_not_warn(tmp_path: Path) -> None:
    _write(
        tmp_path / "entities" / "questions" / "0001-a.md",
        "---\nid: question:a\norigins:\n"
        "  - type: user\n    independent: true\n"
        "  - type: assistant\n    independent: true\n---\nBody.\n",
    )

    results = list(check_origin_refs(_ctx(tmp_path)))

    assert not any("independent" in message.lower() for message in _messages(results)), _messages(results)
