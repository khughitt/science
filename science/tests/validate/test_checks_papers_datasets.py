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
        f'---\ntype: "paper"\nid: "paper:{slug}"\ntitle: "T"\ndatasets:\n{ds}\n---\n\nBody.\n',
        encoding="utf-8",
    )


def _warnings(results: Iterable[Result]) -> list[str]:
    return [r.message for r in results if r.severity is Severity.WARN]


def test_free_text_paper_dataset_warns(tmp_path: Path) -> None:
    """A free-text paper datasets entry must warn that it blocks commons promotion.

    Regression for fb-2026-05-29-006: free-text 'datasets:' values only failed at
    'commons promote --apply' (after summaries were written); the canonical paper
    schema requires 'dataset:'-prefixed refs. validate now flags it earlier.
    """
    from science_tool.validate.checks.papers import check_papers

    _write_paper(tmp_path, "Smith2025", ["GSE12345 (RNA-seq cohort)"])

    warnings = _warnings(check_papers(_ctx(tmp_path)))
    assert len(warnings) == 1
    assert "Smith2025" in warnings[0]
    assert "GSE12345 (RNA-seq cohort)" in warnings[0]


def test_dataset_ref_paper_does_not_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.papers import check_papers

    _write_paper(tmp_path, "Jones2025", ["dataset:geo-gse12345"])

    assert _warnings(check_papers(_ctx(tmp_path))) == []


def test_paper_without_datasets_does_not_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.papers import check_papers

    papers_dir = tmp_path / "doc" / "background" / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    papers_dir.joinpath("Nodata2025.md").write_text(
        '---\ntype: "paper"\nid: "paper:Nodata2025"\ntitle: "T"\n---\n\nBody.\n',
        encoding="utf-8",
    )

    assert _warnings(check_papers(_ctx(tmp_path))) == []
