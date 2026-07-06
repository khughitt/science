from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from science_tool.validate import Result, Severity, ValidateContext


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


def _write_paper(root: Path, slug: str, datasets: list[str]) -> None:
    papers_dir = root / "entities" / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    ds = "\n".join(f"  - {entry!r}" for entry in datasets)
    papers_dir.joinpath(f"{slug}.md").write_text(
        f'---\nkind: "paper"\nid: "paper:{slug}"\ntitle: "T"\ndatasets:\n{ds}\n---\n\nBody.\n',
        encoding="utf-8",
    )


def _warnings(results: Iterable[Result]) -> list[str]:
    return [r.message for r in results if r.severity is Severity.WARN]


def test_paper_datasets_are_not_checked_by_paper_summary_check(tmp_path: Path) -> None:
    from science_tool.validate.checks.papers import check_papers

    _write_paper(tmp_path, "Jones2025", ["dataset:geo-gse12345"])

    assert _warnings(check_papers(_ctx(tmp_path))) == []


def test_paper_without_datasets_does_not_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.papers import check_papers

    papers_dir = tmp_path / "doc" / "background" / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    papers_dir.joinpath("Nodata2025.md").write_text(
        '---\nkind: "paper"\nid: "paper:Nodata2025"\ntitle: "T"\n---\n\nBody.\n',
        encoding="utf-8",
    )

    assert _warnings(check_papers(_ctx(tmp_path))) == []
