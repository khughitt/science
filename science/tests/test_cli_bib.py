"""CLI tests for `science bib add`."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.bibliography import load_bib_keys
from science_tool.cli import main

ENTRY = "@article{Smith2024,\n  title={A Test Paper},\n  author={Smith, Jane},\n  year={2024}\n}"


def test_bib_add_from_stdin(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["bib", "add", "--project-root", str(tmp_path)],
        input=ENTRY,
    )
    assert result.exit_code == 0, result.output
    assert load_bib_keys(tmp_path) == {"Smith2024"}
    assert "added" in result.output.lower()


def test_bib_add_from_entry_file(tmp_path: Path) -> None:
    entry_file = tmp_path / "entry.bib"
    entry_file.write_text(ENTRY, encoding="utf-8")
    result = CliRunner().invoke(
        main,
        ["bib", "add", "--project-root", str(tmp_path), "--entry-file", str(entry_file)],
    )
    assert result.exit_code == 0, result.output
    assert load_bib_keys(tmp_path) == {"Smith2024"}


def test_bib_add_idempotent_exists_json(tmp_path: Path) -> None:
    CliRunner().invoke(main, ["bib", "add", "--project-root", str(tmp_path)], input=ENTRY)
    result = CliRunner().invoke(
        main,
        ["bib", "add", "--project-root", str(tmp_path), "--json"],
        input=ENTRY,
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == {"key": "Smith2024", "action": "exists", "path": str(tmp_path / "papers" / "references.bib")}


def test_bib_add_rejects_unparseable_entry(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        ["bib", "add", "--project-root", str(tmp_path)],
        input="not a bibtex entry",
    )
    assert result.exit_code != 0
    assert "BibTeX key" in result.output
