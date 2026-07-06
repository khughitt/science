from pathlib import Path

import pytest
from rdflib import Dataset, Namespace
from rdflib.namespace import RDF, SKOS

from conftest import build_entity_graph

PROJECT_NS = Namespace("http://example.org/project/")
SCI = Namespace("http://example.org/science/vocab/")


def _knowledge_graph(trig_path: Path):
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    return dataset.graph(PROJECT_NS["graph/knowledge"])


def test_build_entity_graph_authors_concept(tmp_path: Path) -> None:
    trig_path = build_entity_graph(
        tmp_path,
        [
            {
                "kind": "concept",
                "id": "treatment-response",
                "frontmatter": {"title": "Treatment response", "status": "active"},
                "body": "Project-local concept.",
            }
        ],
    )

    knowledge = _knowledge_graph(trig_path)

    assert (PROJECT_NS["concept/treatment-response"], RDF.type, SCI.Concept) in knowledge


def test_build_entity_graph_materializes_structured_relations(tmp_path: Path) -> None:
    trig_path = build_entity_graph(
        tmp_path,
        [
            {
                "kind": "concept",
                "id": "parent",
                "frontmatter": {"title": "Parent", "status": "active"},
                "body": "Parent concept.",
            },
            {
                "kind": "concept",
                "id": "child",
                "frontmatter": {"title": "Child", "status": "active"},
                "body": "Child concept.",
            },
        ],
        relations=[
            {
                "subject": "concept:child",
                "predicate": "skos:broader",
                "object": "concept:parent",
                "graph_layer": "graph/knowledge",
            }
        ],
    )

    knowledge = _knowledge_graph(trig_path)

    assert (PROJECT_NS["concept/child"], SKOS.broader, PROJECT_NS["concept/parent"]) in knowledge


def test_build_entity_graph_rejects_malformed_relation_data(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"relations\[0\]\.object must be a non-empty string"):
        build_entity_graph(
            tmp_path,
            [
                {
                    "kind": "concept",
                    "id": "child",
                    "frontmatter": {"title": "Child", "status": "active"},
                    "body": "Child concept.",
                }
            ],
            relations=[
                {
                    "subject": "concept:child",
                    "predicate": "skos:broader",
                    "target": "concept:parent",
                    "graph_layer": "graph/knowledge",
                }
            ],
        )
