"""Round-trip test: base-Entity reasoning metadata authored in frontmatter reaches the provenance graph."""

from __future__ import annotations

from pathlib import Path

from rdflib import Dataset, URIRef

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _write(tmp_path: Path, rel: str, body: str) -> None:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _load_dataset(project: Path) -> Dataset:
    trig_path = materialize_graph(project)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    return dataset


def _minimal_project(tmp_path: Path) -> Path:
    """Write a minimal project with a proposition that has base-Entity reasoning metadata."""
    _write(tmp_path, "science.yaml", "name: test\nknowledge_profiles:\n  local: local\n")

    _write(
        tmp_path,
        "doc/propositions/p.md",
        """---
id: proposition:p
kind: proposition
title: "Proposition P"
project: test
ontology_terms: []
related: []
source_refs: []
created: 2026-05-01
updated: 2026-05-01
independence_group: g1
proxy_directness: indirect
---
""",
    )

    return tmp_path


def test_independence_group_in_provenance(tmp_path: Path) -> None:
    """independence_group: g1 → sci:independenceGroup Literal in provenance graph."""
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    prop_uri = URIRef(PROJECT_NS["proposition/p"])
    values = {str(o) for _, _, o in provenance.triples((prop_uri, SCI_NS.independenceGroup, None))}
    assert "g1" in values, f"Expected sci:independenceGroup 'g1', got {values}"


def test_proxy_directness_in_provenance(tmp_path: Path) -> None:
    """proxy_directness: indirect → sci:proxyDirectness Literal in provenance graph."""
    project = _minimal_project(tmp_path)
    dataset = _load_dataset(project)
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    prop_uri = URIRef(PROJECT_NS["proposition/p"])
    values = {str(o) for _, _, o in provenance.triples((prop_uri, SCI_NS.proxyDirectness, None))}
    assert "indirect" in values, f"Expected sci:proxyDirectness 'indirect', got {values}"
