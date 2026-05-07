"""Tests for chain-link -> bears_on inverse derivation and audits derivation."""

from __future__ import annotations

from rdflib import Dataset, URIRef

from science_tool.graph.freshness import derive_bears_on_from_chain_links
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _u(local: str) -> URIRef:
    return URIRef(PROJECT_NS[local])


def _make_dataset_with(triples) -> Dataset:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for s, p, o in triples:
        knowledge.add((s, p, o))
    return ds


def _bears_on_pairs(ds: Dataset) -> set[tuple[str, str]]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}


def test_chain_link_emits_inverse_bears_on() -> None:
    """structural-chain sci:hasLink mechanism -> mechanism bears_on chain (inverse)."""
    ds = _make_dataset_with([(_u("chain/abc"), SCI_NS.hasLink, _u("mechanism/a"))])
    derive_bears_on_from_chain_links(ds)
    pairs = _bears_on_pairs(ds)
    assert (str(_u("mechanism/a")), str(_u("chain/abc"))) in pairs


def test_three_link_chain_emits_three_bears_on() -> None:
    chain = _u("chain/abc")
    ds = _make_dataset_with(
        [
            (chain, SCI_NS.hasLink, _u("mechanism/a")),
            (chain, SCI_NS.hasLink, _u("mechanism/b")),
            (chain, SCI_NS.hasLink, _u("mechanism/c")),
        ]
    )
    derive_bears_on_from_chain_links(ds)
    pairs = _bears_on_pairs(ds)
    assert (str(_u("mechanism/a")), str(chain)) in pairs
    assert (str(_u("mechanism/b")), str(chain)) in pairs
    assert (str(_u("mechanism/c")), str(chain)) in pairs
