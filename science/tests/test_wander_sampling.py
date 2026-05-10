from __future__ import annotations

from datetime import date
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


def test_sample_for_walk_returns_attention_candidates(tmp_path: Path) -> None:
    graph_path = _write_graph(tmp_path, _two_hypothesis_dataset())

    sample = sample_for_walk(graph_path=graph_path, n=2, seed=7, today=date(2026, 5, 9))

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

    first = sample_for_walk(graph_path=graph_path, n=1, seed=7, today=date(2026, 5, 9))
    second = sample_for_walk(graph_path=graph_path, n=1, seed=7, today=date(2026, 5, 9))

    assert [c.entity_id for c in first] == [c.entity_id for c in second]


def test_sample_for_walk_respects_kind_filter(tmp_path: Path) -> None:
    dataset = _two_hypothesis_dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    proposition = _u("proposition/p1")
    knowledge.add((proposition, RDF.type, SCI_NS.Proposition))
    knowledge.add((proposition, SKOS.prefLabel, Literal("A claim")))
    knowledge.add((proposition, SCI_NS.freshnessState, Literal("fresh")))
    graph_path = _write_graph(tmp_path, dataset)

    sample = sample_for_walk(graph_path=graph_path, n=5, seed=7, today=date(2026, 5, 9), kinds={"proposition"})

    assert {c.entity_id for c in sample} == {"proposition:p1"}


def test_sample_for_walk_errors_on_missing_graph(tmp_path: Path) -> None:
    missing = tmp_path / "no-such.trig"

    with pytest.raises(WanderSamplerError) as excinfo:
        sample_for_walk(graph_path=missing, n=3, seed=7, today=date(2026, 5, 9))

    assert "science graph build" in str(excinfo.value)
