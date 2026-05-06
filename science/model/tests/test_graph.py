from science_model.graph import GraphData, GraphEdge, GraphNode


def test_graph_data_structure():
    node = GraphNode(
        id="http://example.org/project/concept/foo",
        label="Foo",
        type="Concept",
        importance=0.8,
        graph_layer="graph/knowledge",
    )
    edge = GraphEdge(
        source=node.id,
        target="http://example.org/project/concept/bar",
        predicate="skos:related",
        graph_layer="graph/knowledge",
    )
    gd = GraphData(
        nodes=[node],
        edges=[edge],
        domains={"genomics": "#e06c75"},
        lod=0.5,
        total_nodes=10,
    )
    assert gd.total_nodes == 10
    assert gd.nodes[0].boundary_role is None
