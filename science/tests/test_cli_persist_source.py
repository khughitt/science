"""Tests for `science paper persist-source` and the `persist_source` function."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from click.testing import CliRunner

from science_tool.annotation.source_text import AcquiredSource, Passage, SourcePassages, persist_source
from science_tool.cli import main
from science_tool.paper_fetch import FetchConfig


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _cfg(tmp_path: Path) -> FetchConfig:
    return FetchConfig(email="t@example.com", cache_dir=tmp_path / "cache")


def _write_paper(project_root: Path, citekey: str, *, doi: str, pmid: str) -> Path:
    papers_dir = project_root / "entities" / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    path = papers_dir / f"{citekey}.md"
    path.write_text(
        f'---\nid: paper:{citekey}\ntitle: {citekey}\ndoi: {doi}\npmid: "{pmid}"\n---\n\n## Key Findings\n\nx\n',
        encoding="utf-8",
    )
    return path


_BIOC = {
    "PubTator3": [
        {
            "infons": {"_release": "2024.01"},
            "passages": [
                {"offset": 0, "text": "Title here", "infons": {"type": "title"}},
                {"offset": 11, "text": "Abstract body.", "infons": {"type": "abstract"}},
            ],
        }
    ]
}


def _bioc_handler(req: httpx.Request) -> httpx.Response:
    if req.url.host == "www.ncbi.nlm.nih.gov":
        return httpx.Response(200, json=_BIOC)
    if req.url.host == "www.ebi.ac.uk":
        return httpx.Response(
            200, json={"resultList": {"result": [{"license": "CC-BY-4.0"}]}}
        )
    raise AssertionError(f"unexpected host {req.url.host}")


# ---------------------------------------------------------------------------
# Direct persist_source call — success path
# ---------------------------------------------------------------------------


def test_persist_source_writes_source_md(tmp_path: Path) -> None:
    """persist_source writes <citekey>.source.md with ## Abstract when given an http client."""
    project = tmp_path / "proj"
    _write_paper(project, "Smith2024", doi="10.1038/foo-1", pmid="123456")

    out = persist_source(
        project_root=project,
        identifier="10.1038/foo-1",
        cfg=_cfg(tmp_path),
        http=_make_client(_bioc_handler),
    )

    assert out == project / "entities" / "papers" / "Smith2024.source.md"
    assert out.is_file()
    assert "## Abstract" in out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI no-match path — CliRunner, no HTTP needed
# ---------------------------------------------------------------------------


def test_persist_source_no_match_fails_loud(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write_paper(project, "Smith2024", doi="10.1038/foo-1", pmid="123456")
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "paper",
            "persist-source",
            "10.9999/missing",
            "--project-root",
            str(project),
            "--email",
            "t@example.com",
        ],
    )
    assert result.exit_code != 0
    assert "no paper entity" in result.output


# ---------------------------------------------------------------------------
# CLI success wiring — monkeypatch acquire_source_text (test-time only)
# ---------------------------------------------------------------------------


def test_persist_source_cli_wiring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI → persist_source → acquire_source_text wired correctly end-to-end."""
    project = tmp_path / "proj"
    _write_paper(project, "Smith2024", doi="10.1038/foo-1", pmid="123456")

    canned = AcquiredSource(
        abstract=SourcePassages(
            passages=(
                Passage(section="title", bioc_offset=0, text="Title here"),
                Passage(section="abstract", bioc_offset=11, text="Abstract body."),
            ),
            release="2024.01",
        ),
        fulltext=None,
        retrieved_from="pubtator3",
        license="CC-BY-4.0",
        licensed=True,
    )

    def _fake_acquire(**kwargs: Any) -> AcquiredSource:
        return canned

    monkeypatch.setattr(
        "science_tool.annotation.source_text.acquire_source_text",
        _fake_acquire,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "paper",
            "persist-source",
            "10.1038/foo-1",
            "--project-root",
            str(project),
            "--email",
            "t@example.com",
        ],
    )
    assert result.exit_code == 0, result.output
    out = project / "entities" / "papers" / "Smith2024.source.md"
    assert out.is_file()
    assert "## Abstract" in out.read_text(encoding="utf-8")
