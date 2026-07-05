# science/tests/test_archive_cli.py
"""CLI: science entities archive / unarchive (report-then-apply) (P3)."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _superseded(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    (d / "0001-x.md").write_text("---\nid: interpretation:0001-x\nkind: interpretation\nstatus: superseded\n---\n", encoding="utf-8")


def test_archive_report_then_apply(tmp_path: Path) -> None:
    _superseded(tmp_path)
    r1 = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path)])
    assert r1.exit_code == 0, r1.output
    assert "interpretation:0001-x" in r1.output
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()  # dry run

    r2 = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--apply"])
    assert r2.exit_code == 0, r2.output
    assert (tmp_path / "entities" / "_archive" / "interpretations" / "0001-x.md").exists()


def test_unarchive_restores(tmp_path: Path) -> None:
    _superseded(tmp_path)
    CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--apply"])
    r = CliRunner().invoke(main, ["entities", "unarchive", "interpretation:0001-x", "--project-root", str(tmp_path), "--apply"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "entities" / "interpretations" / "0001-x.md").exists()
