"""Unit tests for the shared supersedes-graph pass (P2 refactor of P1)."""

from __future__ import annotations

from pathlib import Path

import yaml


def _write(root: Path, kind_dir: str, name: str, fm: dict) -> None:
    d = root / "entities" / kind_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nbody\n", encoding="utf-8"
    )


def _supersedes(target: str) -> dict:
    return {"predicate": "sci:supersedes", "target": target}


def test_build_supersedes_graph_linear_chain(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: g\n", encoding="utf-8")
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "kind": "interpretation"})
    _write(tmp_path, "interpretations", "i-v4", {"id": "interpretation:i-v4", "kind": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})
    _write(tmp_path, "interpretations", "i-v5", {"id": "interpretation:i-v5", "kind": "interpretation", "relations": [_supersedes("interpretation:i-v4")]})

    from science_tool.consolidation import build_supersedes_graph, iter_entity_frontmatter

    graph = build_supersedes_graph(iter_entity_frontmatter(tmp_path))
    assert len(graph.linear) == 1
    chain = graph.linear[0]
    assert chain.survivor == "interpretation:i-v5"
    assert chain.superseded == ("interpretation:i-v3", "interpretation:i-v4")
    assert graph.non_linear == ()
    assert graph.kind_by_id["interpretation:i-v3"] == "interpretation"
    assert graph.status_by_id["interpretation:i-v3"] is None


def test_build_supersedes_graph_non_linear(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: g\n", encoding="utf-8")
    _write(tmp_path, "interpretations", "i-v3", {"id": "interpretation:i-v3", "kind": "interpretation"})
    _write(tmp_path, "interpretations", "i-a", {"id": "interpretation:i-a", "kind": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})
    _write(tmp_path, "interpretations", "i-b", {"id": "interpretation:i-b", "kind": "interpretation", "relations": [_supersedes("interpretation:i-v3")]})

    from science_tool.consolidation import build_supersedes_graph, iter_entity_frontmatter

    graph = build_supersedes_graph(iter_entity_frontmatter(tmp_path))
    assert graph.linear == ()
    assert len(graph.non_linear) == 1
    assert graph.non_linear[0].nodes == ("interpretation:i-a", "interpretation:i-b", "interpretation:i-v3")
