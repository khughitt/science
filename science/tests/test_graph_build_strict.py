"""Tests for strict graph-build mode."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_doc_data_package_files_do_not_trigger_strict_preflight(tmp_path: Path) -> None:
    _seed(tmp_path)
    _question_md(tmp_path, "q1.md", "question:q1")
    f = tmp_path / "doc" / "data-packages" / "u.md"
    f.parent.mkdir(parents=True)
    f.write_text(
        '---\nid: "data-package:u"\ntype: "data-package"\ntitle: "U"\nstatus: "active"\n---\n',
        encoding="utf-8",
    )
    from science_tool.graph.materialize import materialize_graph

    assert materialize_graph(tmp_path, strict=True) == tmp_path / "knowledge" / "graph.trig"


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: proj\nprofile: research\nprofiles: {local: local}\n", encoding="utf-8")


def _question_md(root: Path, filename: str, cid: str) -> None:
    p = root / "entities" / "questions" / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\nid: "{cid}"\nkind: "question"\ntitle: "{cid}"\n---\n', encoding="utf-8")


def test_strict_build_blocks_genuine_duplicate(tmp_path: Path) -> None:
    # two NON-deprecated owners of one id is a genuine §B1 collision — still blocked, now
    # at the audit stage (ValueError) rather than at load (EntityIdentityCollisionError).
    from science_tool.graph.materialize import materialize_graph

    _seed(tmp_path)
    _question_md(tmp_path, "q1.md", "question:q1")
    _question_md(tmp_path, "q1-dup.md", "question:q1")
    with pytest.raises(ValueError):
        materialize_graph(tmp_path, strict=True)
