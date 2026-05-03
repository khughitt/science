"""Freshness engine — bears_on derivation and EpistemicFreshness computation.

Implements Phase 1 of docs/plans/2026-05-03-epistemic-dependency-graph-design.md.
Operates over an rdflib Dataset that has already been populated with the
project's typed relations and provenance triples by `materialize_graph()`.

Public surface:
    derive_bears_on_from_typed_edges(dataset)
    derive_bears_on_from_provenance(dataset, *, kind_class)
    close_bears_on(dataset, *, kind_class)
    derive_freshness(dataset, *, entities, kind_class, today)
"""

from __future__ import annotations

from rdflib import Dataset, URIRef

from science_tool.graph.store import CITO_NS, PROJECT_NS, SCI_NS


def derive_bears_on_from_typed_edges(dataset: Dataset) -> None:
    """Emit `bears_on` triples derived from the project's typed relations.

    Reads the knowledge layer; writes new `sci:bearsOn` triples back into the
    same layer. Idempotent: re-running on a dataset that already contains
    derived edges does not emit duplicates (rdflib graphs are sets).

    Rules:
      ?s sci:tests           ?t  -> ?s bears_on ?t
      ?s cito:supports       ?t  -> ?s bears_on ?t
      ?s cito:disputes       ?t  -> ?s bears_on ?t
      ?s sci:grounds         ?t  -> ?s bears_on ?t
      ?f sci:groundedBy      ?s  -> ?s bears_on ?f          (inverse)
      ?c sci:contains        ?m  -> ?m bears_on ?c          (inverse)
      ?s sci:synthesizes     ?t  -> ?t bears_on ?s          (inverse)
      ?m sci:hasProposition  ?p  -> ?p bears_on ?m          (inverse)
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    direct_predicates: list[URIRef] = [
        SCI_NS.tests,
        CITO_NS.supports,
        CITO_NS.disputes,
        SCI_NS.grounds,
    ]
    inverse_predicates: list[URIRef] = [
        SCI_NS.groundedBy,
        SCI_NS.contains,
        SCI_NS.synthesizes,
        SCI_NS.hasProposition,
    ]

    for predicate in direct_predicates:
        for s, _, o in knowledge.triples((None, predicate, None)):
            knowledge.add((s, SCI_NS.bearsOn, o))
    for predicate in inverse_predicates:
        for s, _, o in knowledge.triples((None, predicate, None)):
            knowledge.add((o, SCI_NS.bearsOn, s))
