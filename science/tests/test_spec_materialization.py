# science/tests/test_spec_materialization.py
"""Spec graph guards: a spec materializes as a node, a wired spec->spec supersedes edge
materializes, and (post-S3b flip) an ordinary spec: metadata reference resolves and
materializes an edge to the spec node."""
from __future__ import annotations

import sys
from pathlib import Path

if "conftest" in sys.modules and not hasattr(sys.modules["conftest"], "build_entity_graph"):
    del sys.modules["conftest"]
from conftest import build_entity_graph
from rdflib.namespace import RDF, SKOS

from science_tool.graph.store import PROJECT_NS, SCI_NS, _graph_uri, _load_dataset


def _spec_entity(local_part: str, title: str):
    frontmatter = {"title": title, "status": "active", "related": [], "source_refs": []}
    return {"kind": "spec", "id": local_part, "frontmatter": frontmatter, "body": f"{title}\n"}


def test_spec_entity_materializes_as_a_graph_node(tmp_path: Path) -> None:
    graph_path = build_entity_graph(tmp_path, [_spec_entity("0001-design", "Design")])

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    spec_uri = PROJECT_NS["spec/0001-design"]

    assert (spec_uri, RDF.type, SCI_NS.Spec) in knowledge


def test_spec_to_spec_supersedes_edge_materializes(tmp_path: Path) -> None:
    graph_path = build_entity_graph(
        tmp_path,
        [_spec_entity("0001-old", "Old"), _spec_entity("0002-new", "New")],
        relations=[
            {"subject": "spec:0002-new", "predicate": "sci:supersedes", "object": "spec:0001-old"}
        ],
    )

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    new_uri = PROJECT_NS["spec/0002-new"]
    old_uri = PROJECT_NS["spec/0001-old"]

    assert (new_uri, SCI_NS.supersedes, old_uri) in knowledge


def test_ordinary_spec_metadata_reference_materializes_edge(tmp_path: Path) -> None:
    # S3b flip: spec is REMOVED from _ANNOTATION_REF_PREFIXES, so a `spec:` pointer in an
    # ordinary metadata field (`related`) is no longer skipped by `_add_relations` (via
    # is_metadata_reference) -- it resolves to the existing spec node and materializes a
    # SKOS.related edge to it.
    question = {
        "kind": "question",
        "id": "0001-ask",
        "frontmatter": {
            "title": "Ask",
            "status": "active",
            "related": ["spec:0001-design"],  # existing spec target, now resolved
            "source_refs": [],
        },
        "body": "Ask\n",
    }
    graph_path = build_entity_graph(
        tmp_path, [_spec_entity("0001-design", "Design"), question]
    )

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    question_uri = PROJECT_NS["question/0001-ask"]
    spec_uri = PROJECT_NS["spec/0001-design"]

    # The spec node exists on its own...
    assert (spec_uri, RDF.type, SCI_NS.Spec) in knowledge
    # ...and the metadata `related` pointer now materializes an edge to it.
    assert (question_uri, SKOS.related, spec_uri) in knowledge
