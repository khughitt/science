# science/tests/test_search_cli.py
"""science search --archived reads the index; fails loud without --archived (P3)."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.archive import ArchiveRow, append_row, archive_index_path
from science_tool.cli import main


def _seed(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    append_row(archive_index_path(tmp_path), ArchiveRow(op="archive", id="interpretation:0002-dag-v1",
               kind="interpretation", title="Parameter derivation DAG", aliases=["dag-old"],
               original_path="entities/interpretations/0002-dag-v1.md", archived_at="T1"))


def test_search_archived_matches_title(tmp_path: Path) -> None:
    _seed(tmp_path)
    r = CliRunner().invoke(main, ["search", "derivation", "--archived", "--project-root", str(tmp_path), "--format", "json"])
    assert r.exit_code == 0, r.output
    hits = json.loads(r.output)
    assert [h["id"] for h in hits] == ["interpretation:0002-dag-v1"]


def test_search_archived_matches_alias(tmp_path: Path) -> None:
    _seed(tmp_path)
    r = CliRunner().invoke(main, ["search", "dag-old", "--archived", "--project-root", str(tmp_path), "--format", "json"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)[0]["id"] == "interpretation:0002-dag-v1"


def test_search_without_archived_fails_loud(tmp_path: Path) -> None:
    _seed(tmp_path)
    r = CliRunner().invoke(main, ["search", "derivation", "--project-root", str(tmp_path)])
    assert r.exit_code != 0
    assert "--archived" in r.output
