"""Tests for strict graph-build mode (Task 8.5)."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_strict_build_fails_on_unmigrated_data_package(tmp_path: Path) -> None:
    f = tmp_path / "doc" / "data-packages" / "u.md"
    f.parent.mkdir(parents=True)
    f.write_text(
        '---\nid: "data-package:u"\ntype: "data-package"\ntitle: "U"\nstatus: "active"\n---\n',
        encoding="utf-8",
    )
    from science_tool.graph.materialize import materialize_graph

    with pytest.raises(RuntimeError) as exc_info:
        materialize_graph(tmp_path, strict=True)
    assert "data-package:u" in str(exc_info.value)
    assert "no longer supported" in str(exc_info.value)


def test_strict_build_passes_on_superseded(tmp_path: Path) -> None:
    f = tmp_path / "doc" / "data-packages" / "s.md"
    f.parent.mkdir(parents=True)
    f.write_text(
        '---\nid: "data-package:s"\ntype: "data-package"\ntitle: "S"\nstatus: "superseded"\n'
        'superseded_by: "research-package:s"\n---\n',
        encoding="utf-8",
    )
    from science_tool.graph.materialize import materialize_graph

    # No RuntimeError for strict mode when all entries are superseded.
    # The build may fail for other reasons (no sources, no graph file, etc.) —
    # we only care that the strict-mode check itself does not raise RuntimeError.
    try:
        materialize_graph(tmp_path, strict=True)
    except RuntimeError as exc:
        pytest.fail(f"strict mode raised RuntimeError unexpectedly: {exc}")
    except Exception:
        pass  # Other errors (missing sources, graph path, etc.) are expected in a minimal tmp dir


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
