# science/tests/test_archive_acceptance.py
"""End-to-end P3 invariant: archive a referenced superseded entity, then
validate + graph build stay healthy and the file is not live (P3)."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.sources import load_project_sources

rdflib = pytest.importorskip("rdflib")


def _seed(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    d = tmp_path / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    # live entity references the soon-to-be-archived one via related + relations + source_refs
    (d / "0001-live.md").write_text(
        "---\nid: interpretation:0001-live\nkind: interpretation\ntitle: Live\nstatus: complete\n"
        "related:\n  - interpretation:0002-gone\n"
        "source_refs:\n  - interpretation:0002-gone\n"
        "relations:\n  - predicate: sci:supersedes\n    target: interpretation:0002-gone\n---\n",
        encoding="utf-8")
    (d / "0002-gone.md").write_text(
        "---\nid: interpretation:0002-gone\nkind: interpretation\nstatus: superseded\ntitle: Gone v1\n---\n",
        encoding="utf-8")


def test_archive_then_file_not_live(tmp_path: Path) -> None:
    _seed(tmp_path)
    r = CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--apply"])
    assert r.exit_code == 0, r.output
    ids = {e.canonical_id for e in load_project_sources(tmp_path).entities}
    assert "interpretation:0002-gone" not in ids        # not scanned as a live entity
    assert "interpretation:0001-live" in ids


def test_archive_then_graph_edge_and_stub(tmp_path: Path) -> None:
    _seed(tmp_path)
    CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--apply"])
    from science_tool.graph.materialize import materialize_graph
    text = materialize_graph(tmp_path, strict=False).read_text(encoding="utf-8")
    assert "ArchivedEntity" in text
    assert "Gone v1" in text


def test_archive_then_validate_no_new_dangling(tmp_path: Path) -> None:
    _seed(tmp_path)
    CliRunner().invoke(main, ["entities", "archive", "--project-root", str(tmp_path), "--apply"])
    from science_tool.validate.checks.cross_references import check_archive_index, check_cross_references
    from science_tool.validate.context import ValidateContext
    ctx = ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)
    # (a) the archived ref resolves — not reported dangling
    xref = [r.message for r in check_cross_references(ctx)]
    assert not any("0002-gone" in m and "not found" in m for m in xref)
    # (b) the archive-index subcheck reports the archive consistent (no ERRORs)
    from science_tool.validate.result import Severity
    arch = list(check_archive_index(ctx))
    assert not any(r.severity == Severity.ERROR for r in arch)
