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
from rdflib.namespace import PROV

from science_model.entities import EntityClass
from science_tool.graph.store import CITO_NS, PROJECT_NS, SCI_NS


def derive_bears_on_from_typed_edges(
    dataset: Dataset,
    *,
    kind_class: dict[str, EntityClass],
) -> None:
    """Emit `bears_on` triples derived from the project's typed relations.

    `kind_class` maps an entity URI (as str) to its EntityClass; required for
    the `has_participant` rule's epistemic filter.

    See module docstring for the full rule list.

    Rules:
      ?s sci:tests           ?t  -> ?s bears_on ?t
      ?s cito:supports       ?t  -> ?s bears_on ?t
      ?s cito:disputes       ?t  -> ?s bears_on ?t
      ?s sci:grounds         ?t  -> ?s bears_on ?t
      ?f sci:groundedBy      ?s  -> ?s bears_on ?f                       (inverse)
      ?c sci:contains        ?m  -> ?m bears_on ?c                       (inverse)
      ?s sci:synthesizes     ?t  -> ?t bears_on ?s                       (inverse)
      ?m sci:hasProposition  ?p  -> ?p bears_on ?m                       (inverse)
      ?m sci:hasParticipant  ?p  -> ?p bears_on ?m  iff p is epistemic   (inverse, filtered)
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

    # has_participant: emit only when participant is itself epistemic.
    for s, _, o in knowledge.triples((None, SCI_NS.hasParticipant, None)):
        if kind_class.get(str(o)) == EntityClass.EPISTEMIC:
            knowledge.add((o, SCI_NS.bearsOn, s))


def derive_bears_on_from_provenance(
    dataset: Dataset,
    *,
    kind_class: dict[str, EntityClass],
) -> None:
    """Emit `bears_on` triples from prov:wasDerivedFrom edges.

    Rule: `?d prov:wasDerivedFrom ?s` -> `?s bears_on ?d` iff `?d` is epistemic.
    This is how papers/articles enter the dependency graph, since the core
    profile has no direct paper -> hypothesis edge — paper-to-claim provenance
    flows through `source_refs`/`evidence_refs` and is materialized as
    PROV.wasDerivedFrom by `_add_relations` in `materialize.py`.
    """
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    for s, _, o in provenance.triples((None, PROV.wasDerivedFrom, None)):
        # In materialize.py the *derived* side is the subject of wasDerivedFrom.
        # If the derived entity is epistemic, the source bears on it.
        if kind_class.get(str(s)) == EntityClass.EPISTEMIC:
            knowledge.add((o, SCI_NS.bearsOn, s))
