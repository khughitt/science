from pathlib import Path

import pytest
from rdflib import BNode, Dataset, Literal, URIRef
from rdflib.namespace import RDF

from science_tool.graph.io import save_canonical_graph_dataset


def test_canonical_graph_writer_rejects_blank_nodes(tmp_path: Path) -> None:
    dataset = Dataset()
    graph = dataset.graph(URIRef("https://example.org/graph"))
    graph.add((BNode(), RDF.type, Literal("blank-node-subject")))

    with pytest.raises(ValueError, match="Blank nodes are not supported in canonical graph output"):
        save_canonical_graph_dataset(dataset, tmp_path / "graph.trig")
