"""Tests for typed-edge -> bears_on derivation."""

from __future__ import annotations

from rdflib import Dataset, URIRef

from science_tool.graph.freshness import derive_bears_on_from_typed_edges
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _u(local: str) -> URIRef:
    return URIRef(PROJECT_NS[local])


def _make_dataset_with(triples: list[tuple[URIRef, URIRef, URIRef]]) -> Dataset:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    for s, p, o in triples:
        knowledge.add((s, p, o))
    return ds


def _bears_on_pairs(ds: Dataset) -> set[tuple[str, str]]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {
        (str(s), str(o))
        for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))
    }


def test_tests_emits_bears_on():
    """workflow-run sci:tests hypothesis -> bears_on."""
    ds = _make_dataset_with([(_u("workflow-run/wfr1"), SCI_NS.tests, _u("hypothesis/h1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("workflow-run/wfr1")), str(_u("hypothesis/h1"))) in _bears_on_pairs(ds)


def test_supports_emits_bears_on():
    """observation cito:supports proposition -> bears_on (signed -> unsigned)."""
    from rdflib.namespace import Namespace
    cito = Namespace("http://purl.org/spar/cito/")
    ds = _make_dataset_with([(_u("observation/o1"), cito.supports, _u("proposition/p1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("observation/o1")), str(_u("proposition/p1"))) in _bears_on_pairs(ds)


def test_disputes_emits_bears_on():
    from rdflib.namespace import Namespace
    cito = Namespace("http://purl.org/spar/cito/")
    ds = _make_dataset_with([(_u("proposition/p1"), cito.disputes, _u("hypothesis/h1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("proposition/p1")), str(_u("hypothesis/h1"))) in _bears_on_pairs(ds)


def test_grounds_emits_bears_on():
    """workflow-run sci:grounds observation -> bears_on."""
    ds = _make_dataset_with([(_u("workflow-run/wfr1"), SCI_NS.grounds, _u("observation/o1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("workflow-run/wfr1")), str(_u("observation/o1"))) in _bears_on_pairs(ds)


def test_grounded_by_inverse_emits_bears_on():
    """finding sci:groundedBy workflow-run -> workflow-run bears_on finding."""
    ds = _make_dataset_with([(_u("finding/f1"), SCI_NS.groundedBy, _u("workflow-run/wfr1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("workflow-run/wfr1")), str(_u("finding/f1"))) in _bears_on_pairs(ds)


def test_contains_inverse_emits_bears_on_when_container_is_epistemic():
    """interpretation sci:contains finding -> finding bears_on interpretation."""
    ds = _make_dataset_with([(_u("interpretation/i1"), SCI_NS.contains, _u("finding/f1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("finding/f1")), str(_u("interpretation/i1"))) in _bears_on_pairs(ds)


def test_synthesizes_inverse_emits_bears_on():
    """story sci:synthesizes interpretation -> interpretation bears_on story."""
    ds = _make_dataset_with([(_u("story/s1"), SCI_NS.synthesizes, _u("interpretation/i1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("interpretation/i1")), str(_u("story/s1"))) in _bears_on_pairs(ds)


def test_has_proposition_inverse_emits_bears_on():
    """mechanism sci:hasProposition proposition -> proposition bears_on mechanism."""
    ds = _make_dataset_with([(_u("mechanism/m1"), SCI_NS.hasProposition, _u("proposition/p1"))])
    derive_bears_on_from_typed_edges(ds)
    assert (str(_u("proposition/p1")), str(_u("mechanism/m1"))) in _bears_on_pairs(ds)


def test_addresses_does_not_emit_bears_on():
    """question sci:addresses proposition does NOT trigger bears_on (operational direction)."""
    ds = _make_dataset_with([(_u("question/q1"), SCI_NS.addresses, _u("proposition/p1"))])
    derive_bears_on_from_typed_edges(ds)
    assert _bears_on_pairs(ds) == set()


def test_idempotent():
    """Running derivation twice produces the same triples."""
    ds = _make_dataset_with([(_u("workflow-run/wfr1"), SCI_NS.tests, _u("hypothesis/h1"))])
    derive_bears_on_from_typed_edges(ds)
    first = _bears_on_pairs(ds)
    derive_bears_on_from_typed_edges(ds)
    second = _bears_on_pairs(ds)
    assert first == second
