"""The gaps neighborhood must be a neighborhood.

`query_gaps` built its adjacency with `for subj, _, obj in knowledge` -- the predicate
DISCARDED. That admitted `rdf:type`, which made every class node a hub: each hypothesis
sat 1 hop from `sci:Hypothesis` and therefore 2 hops from every OTHER hypothesis. At the
default `hops=2` a "neighborhood" was the entire project.

Observed in mm30 (fb-2026-07-11-010): 29 hypothesis-synthesizer subagents each received
the same six irrelevant `evidential_fragility(contested)` rows regardless of the center
they were given, and each independently worked out that the rows were out of scope and
discarded them. The instrument was wrong and the agents compensated by hand.

The fix is NOT to special-case `rdf:type`. Any predicate whose object is a shared
vocabulary term forms the same hub. The invariant is about the ENDPOINTS: an edge is
admissible iff both of them are project entities.
"""

from pathlib import Path

from rdflib import RDF, Dataset, Literal, Namespace, URIRef

from science_tool.graph.io import SCHEMA_NS, SCI_NS
from science_tool.graph.store import _graph_uri, query_gaps

PROJECT_NS = Namespace("http://example.org/project/")

ALPHA = URIRef(PROJECT_NS["hypothesis/0001-alpha"])
BETA = URIRef(PROJECT_NS["hypothesis/0002-beta"])
GAMMA = URIRef(PROJECT_NS["hypothesis/0003-gamma"])


def _write_graph(tmp_path: Path) -> Path:
    """Three hypotheses. ZERO edges between them. The only thing they share is rdf:type."""
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    for uri, label in ((ALPHA, "Alpha"), (BETA, "Beta"), (GAMMA, "Gamma")):
        k.add((uri, RDF.type, SCI_NS.Hypothesis))
        k.add((uri, SCHEMA_NS.text, Literal(label)))
    out = tmp_path / "graph.trig"
    ds.serialize(destination=str(out), format="trig")
    return out


def test_center_does_not_leak_across_the_rdf_type_hub(tmp_path: Path) -> None:
    """hops=2 must not return every entity of the same rdf:type."""
    graph_path = _write_graph(tmp_path)

    result = query_gaps(graph_path=graph_path, center="hypothesis:0001-alpha", hops=2, limit=50)

    entities = {row["entity"] for row in result.rows}
    assert entities == {"hypothesis:0001-alpha"}, f"center leaked into unrelated hypotheses: {entities}"


def test_rows_are_curies_not_iris(tmp_path: Path) -> None:
    """An IRI row is uncitable: the big-picture validator flags it as
    `nonexistent_reference`, so mm30's subagents had to paraphrase gaps findings as
    ungrounded prose or drop them (fb-2026-07-11-011). The data was in the bundle and
    unusable at the point of use.
    """
    graph_path = _write_graph(tmp_path)

    result = query_gaps(graph_path=graph_path, center="hypothesis:0001-alpha", hops=1, limit=50)

    assert result.rows
    for row in result.rows:
        assert not row["entity"].startswith("http"), f"IRI leaked into a row: {row['entity']}"
    assert result.rows[0]["entity"] == "hypothesis:0001-alpha"


def test_isolated_entity_has_degree_zero(tmp_path: Path) -> None:
    """The `rdf:type` edge was being counted as connectivity, so an entity with NO real
    edges reported `degree=1`. A schema edge is not a claim.
    """
    graph_path = _write_graph(tmp_path)

    result = query_gaps(graph_path=graph_path, center="hypothesis:0001-alpha", hops=1, limit=50)

    row = next(r for r in result.rows if r["entity"] == "hypothesis:0001-alpha")
    assert "degree=0" in row["issues"], f"schema edges still counted as connectivity: {row['issues']}"


def test_a_real_edge_still_connects(tmp_path: Path) -> None:
    """The filter must not sever genuine entity-to-entity edges -- otherwise the walk
    would return the center and nothing else, which is a different way of being wrong.
    """
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))
    for uri, label in ((ALPHA, "Alpha"), (BETA, "Beta")):
        k.add((uri, RDF.type, SCI_NS.Hypothesis))
        k.add((uri, SCHEMA_NS.text, Literal(label)))
    k.add((ALPHA, SCI_NS.bearsOn, BETA))  # a real claim edge
    out = tmp_path / "graph.trig"
    ds.serialize(destination=str(out), format="trig")

    result = query_gaps(graph_path=out, center="hypothesis:0001-alpha", hops=1, limit=50)

    entities = {row["entity"] for row in result.rows}
    assert entities == {"hypothesis:0001-alpha", "hypothesis:0002-beta"}
