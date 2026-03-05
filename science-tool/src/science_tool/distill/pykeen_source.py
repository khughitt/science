from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, SKOS

from science_tool.distill import (
    DEFAULT_SNAPSHOT_DIR,
    SCI_NS,
    bind_common_prefixes,
    write_snapshot,
)

DATASET_NS = Namespace("http://example.org/science/datasets/")


def distill_pykeen(
    *,
    dataset_name: str,
    budget: int | None = None,
    output_path: Path | None = None,
) -> Path:
    """Distill a PyKEEN dataset into a Turtle snapshot.

    If budget is given, select top-N entities by PageRank and retain
    only edges between selected entities. Otherwise, take all triples.
    """
    factory = _load_pykeen_dataset(dataset_name)
    triples = factory.triples  # numpy array of (head, relation, tail) strings

    if budget is not None and budget < len(factory.entity_to_id):
        selected_entities = _pagerank_select(triples, budget)
    else:
        selected_entities = set(factory.entity_to_id.keys())

    g = Graph()
    bind_common_prefixes(g)
    slug = _slug(dataset_name)
    ds_ns = Namespace(f"{DATASET_NS}{slug}/")
    g.bind("ds", ds_ns)

    # Add entity nodes
    for entity in sorted(selected_entities):
        entity_uri = URIRef(ds_ns[_slug(entity)])
        g.add((entity_uri, RDF.type, SCI_NS.Concept))
        g.add((entity_uri, SKOS.prefLabel, Literal(entity)))

    # Add edges between selected entities
    for head, relation, tail in triples:
        if head in selected_entities and tail in selected_entities:
            head_uri = URIRef(ds_ns[_slug(head)])
            tail_uri = URIRef(ds_ns[_slug(tail)])
            rel_uri = URIRef(ds_ns[f"rel/{_slug(relation)}"])
            g.add((head_uri, rel_uri, tail_uri))

    node_count = len(selected_entities)
    total_triples = len(g)

    if output_path is None:
        output_path = DEFAULT_SNAPSHOT_DIR / f"{slug}-core.ttl"

    source_url = f"https://pykeen.readthedocs.io/en/stable/api/pykeen.datasets.{dataset_name}.html"

    return write_snapshot(
        g,
        output_path=output_path,
        name=f"{dataset_name} (PyKEEN distillation, budget={budget or 'all'})",
        source_url=source_url,
        version=f"pykeen:{slug}",
        node_count=node_count,
        triple_count=total_triples,
    )


def _pagerank_select(triples: Any, budget: int) -> set[str]:
    """Select top-N entities by PageRank from the triple set."""
    try:
        import networkx as nx
    except ImportError as exc:
        raise ImportError(
            "networkx is required for budget-based distillation. Install with: uv add --optional distill 'networkx>=3.2'"
        ) from exc

    G = nx.DiGraph()
    for head, relation, tail in triples:
        G.add_edge(head, tail, relation=relation)

    pr = nx.pagerank(G)
    ranked = sorted(pr.items(), key=lambda x: x[1], reverse=True)
    return {entity for entity, _ in ranked[:budget]}


def _load_pykeen_dataset(dataset_name: str) -> Any:
    """Load a PyKEEN dataset by name. Returns a TriplesFactory."""
    try:
        from pykeen.datasets import get_dataset
    except ImportError as exc:
        raise ImportError(
            "pykeen is required for KG distillation. Install with: uv add --optional distill pykeen"
        ) from exc

    dataset = get_dataset(dataset=dataset_name)
    return dataset.training


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
