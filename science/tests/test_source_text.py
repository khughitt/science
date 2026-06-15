"""Tests for the .source.md anchor-surface module (Phase 1)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from science_tool.annotation.source_text import (
    ResolvedPaper,
    SourceTextError,
    resolve_paper_entity,
)


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _write_paper(
    project_root: Path, citekey: str, *, doi: str = "", pmid: str = "",
    subdir: str = "entities/papers",
) -> Path:
    papers_dir = project_root / subdir
    papers_dir.mkdir(parents=True, exist_ok=True)
    path = papers_dir / f"{citekey}.md"
    fm = [f"id: paper:{citekey}", f"title: {citekey}"]
    if doi:
        fm.append(f"doi: {doi}")
    if pmid:
        fm.append(f'pmid: "{pmid}"')
    path.write_text("---\n" + "\n".join(fm) + "\n---\n\n## Key Findings\n\nx\n", encoding="utf-8")
    return path


class TestResolvePaperEntity:
    def test_resolves_by_doi_case_insensitive(self, tmp_path: Path) -> None:
        path = _write_paper(tmp_path, "Smith2024", doi="10.1038/Foo-1")
        resolved = resolve_paper_entity(tmp_path, doi="https://doi.org/10.1038/foo-1", pmid=None)
        assert resolved == ResolvedPaper(
            citekey="Smith2024", path=path, directory=path.parent, doi="10.1038/foo-1", pmid=None
        )

    def test_resolves_by_pmid(self, tmp_path: Path) -> None:
        path = _write_paper(tmp_path, "Jones2025", pmid="123456")
        resolved = resolve_paper_entity(tmp_path, doi=None, pmid="123456")
        assert resolved.citekey == "Jones2025"
        assert resolved.path == path

    def test_resolves_paper_under_doc_background_papers(self, tmp_path: Path) -> None:
        # Real checkouts (this meta repo) store paper summaries outside entities/papers;
        # the resolver must scan every canonical paper subdir, not the policy root.
        path = _write_paper(
            tmp_path, "Meta2026", doi="10.1/meta", subdir="doc/background/papers"
        )
        resolved = resolve_paper_entity(tmp_path, doi="10.1/meta", pmid=None)
        assert resolved.path == path
        assert resolved.directory == tmp_path / "doc" / "background" / "papers"

    def test_carries_entity_pmid_when_resolved_by_doi(self, tmp_path: Path) -> None:
        # Core of the resolver→acquisition contract: a DOI-invoked resolve still
        # surfaces the entity's PMID, so acquisition can prefer PubTator.
        _write_paper(tmp_path, "Smith2024", doi="10.1038/foo-1", pmid="123456")
        resolved = resolve_paper_entity(tmp_path, doi="10.1038/foo-1", pmid=None)
        assert resolved.doi == "10.1038/foo-1"
        assert resolved.pmid == "123456"

    def test_no_match_fails_loud(self, tmp_path: Path) -> None:
        _write_paper(tmp_path, "Smith2024", doi="10.1038/foo-1")
        with pytest.raises(SourceTextError) as exc:
            resolve_paper_entity(tmp_path, doi="10.9999/missing", pmid=None)
        msg = str(exc.value)
        assert "no paper entity" in msg
        assert "10.9999/missing" in msg
        assert "paper-fetch" in msg

    def test_multi_match_fails_loud_naming_both(self, tmp_path: Path) -> None:
        a = _write_paper(tmp_path, "Aaa2024", doi="10.1/dup")
        b = _write_paper(tmp_path, "Bbb2024", doi="10.1/dup")
        with pytest.raises(SourceTextError) as exc:
            resolve_paper_entity(tmp_path, doi="10.1/dup", pmid=None)
        msg = str(exc.value)
        assert str(a) in msg and str(b) in msg

    def test_requires_an_identifier(self, tmp_path: Path) -> None:
        with pytest.raises(SourceTextError):
            resolve_paper_entity(tmp_path, doi=None, pmid=None)
