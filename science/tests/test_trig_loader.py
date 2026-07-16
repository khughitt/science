from __future__ import annotations

import warnings
from pathlib import Path

from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from science_tool.graph.trig import load_trig_dataset_preserving_literals


def test_load_trig_dataset_emits_no_deprecation_warning(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.trig"
    graph_path.write_text("@prefix ex: <https://example.org/> . ex:s ex:p ex:o .")

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        load_trig_dataset_preserving_literals(graph_path)


def test_load_trig_dataset_preserves_structure_resolution_bindings_and_lexical(
    tmp_path: Path,
) -> None:
    graph_path = tmp_path / "graph.trig"
    graph_path.write_text(
        '''@base <https://example.org/base/> .
@prefix ex: <vocab/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<knowledge> {
  <entity> ex:lastReviewed "2026-W18-5"^^xsd:date .
}

<default-entity> ex:label "default graph" .
'''
    )

    dataset = load_trig_dataset_preserving_literals(graph_path)

    predicate = URIRef("https://example.org/base/vocab/lastReviewed")
    knowledge = dataset.graph(URIRef("https://example.org/base/knowledge"))
    reviewed = knowledge.value(URIRef("https://example.org/base/entity"), predicate)
    assert isinstance(reviewed, Literal)
    assert reviewed.datatype == XSD.date
    assert str(reviewed) == "2026-W18-5"
    assert (
        URIRef("https://example.org/base/default-entity"),
        URIRef("https://example.org/base/vocab/label"),
        Literal("default graph"),
    ) in dataset.default_graph
    assert dict(dataset.namespaces())["ex"] == URIRef("https://example.org/base/vocab/")
