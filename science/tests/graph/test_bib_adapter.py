from __future__ import annotations

from pathlib import Path

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.storage_adapters.bib import BibAdapter


def _write_bib(root: Path, text: str) -> None:
    (root / "papers").mkdir(parents=True, exist_ok=True)
    (root / "papers" / "references.bib").write_text(text, encoding="utf-8")


def test_bib_adapter_declares_external_reference() -> None:
    assert BibAdapter.participation_mode is ParticipationMode.EXTERNAL_REFERENCE
    assert BibAdapter.name == "bib"


def test_bib_adapter_discovers_and_loads(tmp_path: Path) -> None:
    _write_bib(
        tmp_path,
        "@article{Smith2024,\n  title = {Cells},\n  year = {2024},\n  doi = {10.1/x},\n}\n",
    )
    adapter = BibAdapter()
    refs = adapter.discover(tmp_path)
    assert [r.line for r in refs] == [0]
    assert refs[0].path == "papers/references.bib"
    raw = adapter.load_raw(refs[0])
    assert raw["kind"] == "paper"
    assert raw["id"] == "paper:Smith2024"
    assert raw["title"] == "Cells"
    assert raw["bibkey"] == "Smith2024"
    assert raw["year"] == 2024
    assert raw["doi"] == "10.1/x"
    assert "url" not in raw  # absent bib field is omitted, not emitted as None


def test_bib_adapter_title_falls_back_to_key(tmp_path: Path) -> None:
    _write_bib(tmp_path, "@misc{NoTitle2000,\n  year = {2000},\n}\n")
    adapter = BibAdapter()
    raw = adapter.load_raw(adapter.discover(tmp_path)[0])
    assert raw["title"] == "NoTitle2000"


def test_bib_adapter_absent_bib_is_empty(tmp_path: Path) -> None:
    assert BibAdapter().discover(tmp_path) == []
