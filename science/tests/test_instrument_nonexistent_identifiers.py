"""A nonexistent identifier must never produce a finding.

These three instruments shared one root cause: ``_resolve_center_entity`` mints a
well-formed URIRef from ANY string without ever consulting the graph -- it takes no
graph argument, so it *cannot* check existence. A typo therefore resolved cleanly,
matched nothing, and the instrument reported that nothing as a result.

Two of them did something worse than return a silent empty. They FABRICATED a finding:

- ``query_gaps`` reported ``structural_fragility(low_connectivity,degree=0)`` -- a
  confident structural claim about an entity that does not exist.
- ``query_evidence`` reported that the target had no supporting or disputing evidence
  -- an affirmative statement about the literature, manufactured from a misspelling.

A withheld finding is bad. An invented one is worse.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import RDF, Dataset, Literal, URIRef

from science_tool.graph.io import CITO_NS, SCHEMA_NS, SCI_NS
from science_tool.graph.store import (
    _graph_uri,
    query_evidence,
    query_gaps,
    query_neighborhood,
    save_graph_dataset,
)

REAL = URIRef("http://example.org/project/proposition/real")
EVIDENCE = URIRef("http://example.org/project/evidence_line/e1")
NEIGHBOR = URIRef("http://example.org/project/proposition/neighbor")

# Resolves to a syntactically valid URI that appears nowhere in the graph.
TYPO = "proposition:doe-not-exist"


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    ds = Dataset()
    k = ds.graph(_graph_uri("graph/knowledge"))

    k.add((REAL, RDF.type, SCI_NS.Proposition))
    k.add((REAL, SCHEMA_NS.text, Literal("a real claim")))
    k.add((NEIGHBOR, RDF.type, SCI_NS.Proposition))
    k.add((NEIGHBOR, SCHEMA_NS.text, Literal("a neighbouring claim")))
    k.add((REAL, CITO_NS.discusses, NEIGHBOR))
    k.add((EVIDENCE, RDF.type, SCI_NS.EvidenceLine))
    k.add((EVIDENCE, CITO_NS.supports, REAL))

    path = tmp_path / "knowledge" / "graph.trig"
    path.parent.mkdir(parents=True)
    save_graph_dataset(ds, path)
    return path


def test_query_gaps_does_not_fabricate_fragility_for_a_nonexistent_center(graph_path: Path) -> None:
    """It used to return ONE row: degree=0 structural fragility, about a typo."""
    result = query_gaps(graph_path=graph_path, center=TYPO, hops=1, limit=50)

    assert result.status == "unwired"
    assert result.code == "center_not_in_graph"
    assert result.rows == []


def test_query_evidence_does_not_claim_a_nonexistent_target_lacks_evidence(graph_path: Path) -> None:
    """It used to report "no supporting or disputing evidence" for a misspelling."""
    result = query_evidence(graph_path=graph_path, target_ref=TYPO, limit=50)

    assert result.status == "unwired"
    assert result.code == "target_not_in_graph"
    assert result.rows == []


def test_query_neighborhood_does_not_report_a_nonexistent_center_as_isolated(graph_path: Path) -> None:
    result = query_neighborhood(
        graph_path=graph_path, center=TYPO, hops=1, graph_layer="graph/knowledge", limit=50
    )

    assert result.status == "unwired"
    assert result.code == "center_not_in_graph"
    assert result.rows == []


# The other half of the ruling: the guard must not simply refuse everything. A center
# that DOES exist still produces real answers -- otherwise "unwired" would be as useless
# as the empty it replaced.


def test_a_real_center_still_returns_rows(graph_path: Path) -> None:
    neighborhood = query_neighborhood(
        graph_path=graph_path,
        center="proposition:real",
        hops=1,
        graph_layer="graph/knowledge",
        limit=50,
    )
    assert neighborhood.status == "ok"
    assert neighborhood.rows

    evidence = query_evidence(graph_path=graph_path, target_ref="proposition:real", limit=50)
    assert evidence.status == "ok"
    assert evidence.rows

    gaps = query_gaps(graph_path=graph_path, center="proposition:real", hops=1, limit=50)
    assert gaps.status in {"ok", "empty"}
