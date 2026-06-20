"""Tests for typed-edge -> bears_on derivation."""

from __future__ import annotations

from rdflib import Dataset, URIRef
from rdflib.namespace import PROV, RDF
from science_model.entities import EntityClass

from science_tool.graph.freshness import (
    close_bears_on,
    derive_bears_on_from_provenance,
    derive_bears_on_from_typed_edges,
)
from science_tool.graph.store import CITO_NS, PROJECT_NS, SCI_NS


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
    return {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}


def test_tests_emits_bears_on():
    """workflow-run sci:tests hypothesis -> bears_on."""
    ds = _make_dataset_with([(_u("workflow-run/wfr1"), SCI_NS.tests, _u("hypothesis/h1"))])
    derive_bears_on_from_typed_edges(ds, kind_class={})
    assert (str(_u("workflow-run/wfr1")), str(_u("hypothesis/h1"))) in _bears_on_pairs(ds)


def test_supports_emits_bears_on():
    """observation cito:supports proposition -> bears_on (signed -> unsigned)."""
    ds = _make_dataset_with([(_u("observation/o1"), CITO_NS.supports, _u("proposition/p1"))])
    derive_bears_on_from_typed_edges(ds, kind_class={})
    assert (str(_u("observation/o1")), str(_u("proposition/p1"))) in _bears_on_pairs(ds)


def test_disputes_emits_bears_on():
    ds = _make_dataset_with([(_u("proposition/p1"), CITO_NS.disputes, _u("hypothesis/h1"))])
    derive_bears_on_from_typed_edges(ds, kind_class={})
    assert (str(_u("proposition/p1")), str(_u("hypothesis/h1"))) in _bears_on_pairs(ds)


def test_grounds_emits_bears_on():
    """workflow-run sci:grounds observation -> bears_on."""
    ds = _make_dataset_with([(_u("workflow-run/wfr1"), SCI_NS.grounds, _u("observation/o1"))])
    derive_bears_on_from_typed_edges(ds, kind_class={})
    assert (str(_u("workflow-run/wfr1")), str(_u("observation/o1"))) in _bears_on_pairs(ds)


def test_grounded_by_inverse_emits_bears_on():
    """finding sci:groundedBy workflow-run -> workflow-run bears_on finding."""
    ds = _make_dataset_with([(_u("finding/f1"), SCI_NS.groundedBy, _u("workflow-run/wfr1"))])
    derive_bears_on_from_typed_edges(ds, kind_class={})
    assert (str(_u("workflow-run/wfr1")), str(_u("finding/f1"))) in _bears_on_pairs(ds)


def test_contains_inverse_emits_bears_on_when_container_is_epistemic():
    """interpretation sci:contains finding -> finding bears_on interpretation."""
    ds = _make_dataset_with([(_u("interpretation/i1"), SCI_NS.contains, _u("finding/f1"))])
    derive_bears_on_from_typed_edges(ds, kind_class={})
    assert (str(_u("finding/f1")), str(_u("interpretation/i1"))) in _bears_on_pairs(ds)


def test_synthesizes_inverse_emits_bears_on():
    """story sci:synthesizes interpretation -> interpretation bears_on story."""
    ds = _make_dataset_with([(_u("story/s1"), SCI_NS.synthesizes, _u("interpretation/i1"))])
    derive_bears_on_from_typed_edges(ds, kind_class={})
    assert (str(_u("interpretation/i1")), str(_u("story/s1"))) in _bears_on_pairs(ds)


def test_has_proposition_inverse_emits_bears_on():
    """mechanism sci:hasProposition proposition -> proposition bears_on mechanism."""
    ds = _make_dataset_with([(_u("mechanism/m1"), SCI_NS.hasProposition, _u("proposition/p1"))])
    derive_bears_on_from_typed_edges(ds, kind_class={})
    assert (str(_u("proposition/p1")), str(_u("mechanism/m1"))) in _bears_on_pairs(ds)


def test_addresses_does_not_emit_bears_on():
    """question sci:addresses proposition does NOT trigger bears_on (operational direction)."""
    ds = _make_dataset_with([(_u("question/q1"), SCI_NS.addresses, _u("proposition/p1"))])
    derive_bears_on_from_typed_edges(ds, kind_class={})
    assert _bears_on_pairs(ds) == set()


def test_idempotent():
    """Running derivation twice produces the same triples."""
    ds = _make_dataset_with([(_u("workflow-run/wfr1"), SCI_NS.tests, _u("hypothesis/h1"))])
    derive_bears_on_from_typed_edges(ds, kind_class={})
    first = _bears_on_pairs(ds)
    derive_bears_on_from_typed_edges(ds, kind_class={})
    second = _bears_on_pairs(ds)
    assert first == second


def test_provenance_emits_bears_on_for_epistemic_target():
    """hypothesis prov:wasDerivedFrom article -> article bears_on hypothesis."""
    ds = _make_dataset_with([])
    provenance = ds.graph(PROJECT_NS["graph/provenance"])
    provenance.add((_u("hypothesis/h1"), PROV.wasDerivedFrom, _u("article/lee2026")))

    kind_class = {
        str(_u("hypothesis/h1")): EntityClass.EPISTEMIC,
        str(_u("article/lee2026")): EntityClass.REFERENCE,
    }
    derive_bears_on_from_provenance(ds, kind_class=kind_class)

    assert (str(_u("article/lee2026")), str(_u("hypothesis/h1"))) in _bears_on_pairs(ds)


def test_provenance_skips_non_epistemic_target():
    """dataset prov:wasDerivedFrom article -> NO bears_on (dataset is operational)."""
    ds = _make_dataset_with([])
    provenance = ds.graph(PROJECT_NS["graph/provenance"])
    provenance.add((_u("dataset/foo"), PROV.wasDerivedFrom, _u("article/lee2026")))

    kind_class = {
        str(_u("dataset/foo")): EntityClass.OPERATIONAL,
        str(_u("article/lee2026")): EntityClass.REFERENCE,
    }
    derive_bears_on_from_provenance(ds, kind_class=kind_class)

    assert _bears_on_pairs(ds) == set()


def test_has_participant_emits_bears_on_for_epistemic_participants_only():
    """mechanism sci:hasParticipant ?p -> ?p bears_on mechanism iff p is epistemic."""
    ds = _make_dataset_with(
        [
            (_u("mechanism/m1"), SCI_NS.hasParticipant, _u("proposition/p1")),
            (_u("mechanism/m1"), SCI_NS.hasParticipant, _u("concept/c1")),
        ]
    )
    kind_class = {
        str(_u("mechanism/m1")): EntityClass.EPISTEMIC,
        str(_u("proposition/p1")): EntityClass.EPISTEMIC,
        str(_u("concept/c1")): EntityClass.REFERENCE,
    }
    derive_bears_on_from_typed_edges(ds, kind_class=kind_class)

    pairs = _bears_on_pairs(ds)
    assert (str(_u("proposition/p1")), str(_u("mechanism/m1"))) in pairs
    assert (str(_u("concept/c1")), str(_u("mechanism/m1"))) not in pairs


def test_close_bears_on_walks_to_epistemic_target():
    """A bears_on B (operational) bears_on C (epistemic) -> A bears_on C."""
    ds = _make_dataset_with([])
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((_u("dataset/d1"), SCI_NS.bearsOn, _u("workflow-run/wfr1")))
    knowledge.add((_u("workflow-run/wfr1"), SCI_NS.bearsOn, _u("hypothesis/h1")))

    kind_class = {
        str(_u("dataset/d1")): EntityClass.OPERATIONAL,
        str(_u("workflow-run/wfr1")): EntityClass.OPERATIONAL,
        str(_u("hypothesis/h1")): EntityClass.EPISTEMIC,
    }
    close_bears_on(ds, kind_class=kind_class)

    assert (str(_u("dataset/d1")), str(_u("hypothesis/h1"))) in _bears_on_pairs(ds)


def test_close_bears_on_terminates_on_cycle():
    """A bears_on B bears_on A (cycle) does not infinite loop and adds nothing extra."""
    ds = _make_dataset_with([])
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((_u("workflow-run/a"), SCI_NS.bearsOn, _u("workflow-run/b")))
    knowledge.add((_u("workflow-run/b"), SCI_NS.bearsOn, _u("workflow-run/a")))
    knowledge.add((_u("workflow-run/a"), SCI_NS.bearsOn, _u("hypothesis/h1")))

    kind_class = {
        str(_u("workflow-run/a")): EntityClass.OPERATIONAL,
        str(_u("workflow-run/b")): EntityClass.OPERATIONAL,
        str(_u("hypothesis/h1")): EntityClass.EPISTEMIC,
    }
    close_bears_on(ds, kind_class=kind_class)

    pairs = _bears_on_pairs(ds)
    # Closure should add: workflow-run/b bears_on hypothesis/h1 (via a)
    assert (str(_u("workflow-run/b")), str(_u("hypothesis/h1"))) in pairs
    # Should NOT loop forever or self-edge.
    self_edges = {(s, o) for s, o in pairs if s == o}
    assert self_edges == set()


def test_close_bears_on_does_not_create_edges_to_operational():
    """Closure only emits edges to epistemic targets."""
    ds = _make_dataset_with([])
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((_u("dataset/d1"), SCI_NS.bearsOn, _u("workflow-run/wfr1")))

    kind_class = {
        str(_u("dataset/d1")): EntityClass.OPERATIONAL,
        str(_u("workflow-run/wfr1")): EntityClass.OPERATIONAL,
    }
    close_bears_on(ds, kind_class=kind_class)

    # Existing edge preserved; no new closure edges since target is not epistemic.
    pairs = _bears_on_pairs(ds)
    assert pairs == {(str(_u("dataset/d1")), str(_u("workflow-run/wfr1")))}


def test_close_bears_on_handles_three_hops():
    """A bears_on B bears_on C bears_on D (epistemic) -> A and B and C all bears_on D."""
    ds = _make_dataset_with([])
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((_u("dataset/d1"), SCI_NS.bearsOn, _u("workflow-run/wfr1")))
    knowledge.add((_u("workflow-run/wfr1"), SCI_NS.bearsOn, _u("workflow-run/wfr2")))
    knowledge.add((_u("workflow-run/wfr2"), SCI_NS.bearsOn, _u("hypothesis/h1")))

    kind_class = {
        str(_u("dataset/d1")): EntityClass.OPERATIONAL,
        str(_u("workflow-run/wfr1")): EntityClass.OPERATIONAL,
        str(_u("workflow-run/wfr2")): EntityClass.OPERATIONAL,
        str(_u("hypothesis/h1")): EntityClass.EPISTEMIC,
    }
    close_bears_on(ds, kind_class=kind_class)

    pairs = _bears_on_pairs(ds)
    h_uri = str(_u("hypothesis/h1"))
    assert (str(_u("dataset/d1")), h_uri) in pairs
    assert (str(_u("workflow-run/wfr1")), h_uri) in pairs
    assert (str(_u("workflow-run/wfr2")), h_uri) in pairs


# ---------------------------------------------------------------------------
# Depth tracking tests (Phase 2 sampling prep)
# ---------------------------------------------------------------------------


def _bears_on_depth(ds: Dataset, source: URIRef, target: URIRef) -> int | None:
    """Return the minimum sci:bearsOnDepth for (source, target), or None if no edge."""
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    depths: list[int] = []
    for bn, _, _ in knowledge.triples((None, RDF.type, SCI_NS.BearsOnEdge)):
        if (bn, SCI_NS.bearsOnSource, source) in knowledge and (bn, SCI_NS.bearsOnTarget, target) in knowledge:
            for _, _, d in knowledge.triples((bn, SCI_NS.bearsOnDepth, None)):
                depths.append(int(str(d)))
    return min(depths) if depths else None


def test_direct_typed_edge_has_depth_one():
    h = _u("hypothesis/h1")
    t = _u("task/t1")
    ds = _make_dataset_with([(t, SCI_NS.tests, h)])
    derive_bears_on_from_typed_edges(ds, kind_class={str(t): EntityClass.OPERATIONAL, str(h): EntityClass.EPISTEMIC})
    assert _bears_on_depth(ds, t, h) == 1


def test_closure_emits_minimum_depth_through_chain():
    # workflow-run grounds observation; observation supports hypothesis.
    # Closure: workflow-run bears_on hypothesis at depth 2.
    wr = _u("workflow-run/w1")
    o = _u("observation/o1")
    h = _u("hypothesis/h1")
    ds = _make_dataset_with([(wr, SCI_NS.grounds, o), (o, CITO_NS.supports, h)])
    kc = {
        str(wr): EntityClass.OPERATIONAL,
        str(o): EntityClass.EPISTEMIC,
        str(h): EntityClass.EPISTEMIC,
    }
    derive_bears_on_from_typed_edges(ds, kind_class=kc)
    close_bears_on(ds, kind_class=kc)
    assert _bears_on_depth(ds, wr, o) == 1
    assert _bears_on_depth(ds, wr, h) == 2


def test_closure_diamond_takes_minimum_depth():
    # A -> B -> D (depth 2); A -> C -> X -> D (depth 3 via three hops). Min should be 2.
    a = _u("workflow-run/a")
    b = _u("observation/b")
    c = _u("observation/c")
    x = _u("observation/x")
    d = _u("hypothesis/d")
    ds = _make_dataset_with(
        [
            (a, SCI_NS.grounds, b),
            (b, CITO_NS.supports, d),
            (a, SCI_NS.grounds, c),
            (c, CITO_NS.supports, x),
            (x, CITO_NS.supports, d),
        ]
    )
    kc = {
        str(a): EntityClass.OPERATIONAL,
        str(b): EntityClass.EPISTEMIC,
        str(c): EntityClass.EPISTEMIC,
        str(x): EntityClass.EPISTEMIC,
        str(d): EntityClass.EPISTEMIC,
    }
    derive_bears_on_from_typed_edges(ds, kind_class=kc)
    close_bears_on(ds, kind_class=kc)
    assert _bears_on_depth(ds, a, d) == 2
