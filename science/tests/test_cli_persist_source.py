"""End-to-end CliRunner tests for `science paper persist-source`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

from science_tool.cli import main


def _make_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


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


def test_persist_source_writes_source_md(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "proj"
    _write_paper(project, "Smith2024", doi="10.1038/foo-1", pmid="123456")

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "www.ncbi.nlm.nih.gov":
            return httpx.Response(200, json=_BIOC)
        if req.url.host == "www.ebi.ac.uk":
            return httpx.Response(
                200, json={"resultList": {"result": [{"license": "CC-BY-4.0"}]}}
            )
        raise AssertionError(f"unexpected host {req.url.host}")

    # Inject the mocked client through the documented test seam.
    monkeypatch.setattr(
        "science_tool.annotation.source_text._test_http_client",
        _make_client(handler),
        raising=False,
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
