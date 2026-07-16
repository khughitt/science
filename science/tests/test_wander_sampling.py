from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from science_tool.graph.io import PROJECT_NS, SCI_NS, save_canonical_graph_dataset
from science_tool.wander.sampling import WanderSamplerError, sample_for_walk


def _u(path: str) -> URIRef:
    return URIRef(PROJECT_NS[path])


def _two_hypothesis_dataset() -> Dataset:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for slug, label in (("h1", "First"), ("h2", "Second")):
        uri = _u(f"hypothesis/{slug}")
        knowledge.add((uri, RDF.type, SCI_NS.Hypothesis))
        knowledge.add((uri, SKOS.prefLabel, Literal(label)))
        knowledge.add((uri, SCI_NS.freshnessState, Literal("fresh")))
    return dataset


def _write_graph(tmp_path: Path, dataset: Dataset) -> Path:
    graph_path = tmp_path / "graph.trig"
    save_canonical_graph_dataset(dataset, graph_path)
    return graph_path


def _authored_last_reviewed_graph(tmp_path: Path, lexical: str) -> Path:
    graph_path = tmp_path / "graph.trig"
    graph_path.write_text(
        f'''@prefix sci: <http://example.org/science/vocab/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/project/graph/knowledge> {{
  <http://example.org/project/hypothesis/h1>
    a sci:Hypothesis ;
    skos:prefLabel "h1" ;
    sci:freshnessState "fresh" ;
    sci:lastReviewed "{lexical}"^^xsd:date .
}}
'''
    )
    return graph_path


def test_sample_for_walk_returns_attention_candidates(tmp_path: Path) -> None:
    graph_path = _write_graph(tmp_path, _two_hypothesis_dataset())

    sample = sample_for_walk(graph_path=graph_path, n=2, seed=7)

    assert len(sample) == 2
    ids = {candidate.entity_id for candidate in sample}
    assert ids == {"hypothesis:h1", "hypothesis:h2"}
    # We need URIs and raw component values downstream — verify they survive.
    for candidate in sample:
        assert candidate.uri.startswith(str(PROJECT_NS))
        assert "incoming_bears_on" in candidate.components
        assert candidate.weight > 0


def test_sample_for_walk_is_seeded(tmp_path: Path) -> None:
    graph_path = _write_graph(tmp_path, _two_hypothesis_dataset())

    first = sample_for_walk(graph_path=graph_path, n=1, seed=7)
    second = sample_for_walk(graph_path=graph_path, n=1, seed=7)

    assert [c.entity_id for c in first] == [c.entity_id for c in second]


def test_sample_for_walk_respects_kind_filter(tmp_path: Path) -> None:
    dataset = _two_hypothesis_dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    proposition = _u("proposition/p1")
    knowledge.add((proposition, RDF.type, SCI_NS.Proposition))
    knowledge.add((proposition, SKOS.prefLabel, Literal("A claim")))
    knowledge.add((proposition, SCI_NS.freshnessState, Literal("fresh")))
    graph_path = _write_graph(tmp_path, dataset)

    sample = sample_for_walk(graph_path=graph_path, n=5, seed=7, kinds={"proposition"})

    assert {c.entity_id for c in sample} == {"proposition:p1"}


def test_sample_for_walk_errors_on_missing_graph(tmp_path: Path) -> None:
    missing = tmp_path / "no-such.trig"

    with pytest.raises(WanderSamplerError) as excinfo:
        sample_for_walk(graph_path=missing, n=3, seed=7)

    assert "science graph build" in str(excinfo.value)


def test_sample_for_walk_preserves_authored_noncanonical_last_reviewed_error(tmp_path: Path) -> None:
    lexical = "2026-W18-5"
    graph_path = _authored_last_reviewed_graph(tmp_path, lexical)

    with pytest.raises(ValueError) as excinfo:
        sample_for_walk(graph_path=graph_path, n=1, seed=7)

    message = str(excinfo.value)
    assert "hypothesis:h1" in message
    assert lexical in message
