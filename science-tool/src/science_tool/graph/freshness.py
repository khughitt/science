"""Freshness engine — bears_on derivation and EpistemicFreshness computation.

Implements Phase 1 of docs/plans/2026-05-03-epistemic-dependency-graph-design.md.
Operates over an rdflib Dataset that has already been populated with the
project's typed relations and provenance triples by `materialize_graph()`.

Public surface:
    derive_bears_on_from_typed_edges(dataset)
    derive_bears_on_from_provenance(dataset, *, kind_class)
    close_bears_on(dataset, *, kind_class)
    derive_freshness(dataset, *, entities, today)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TypedDict

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import PROV, XSD

from science_model.entities import EntityClass
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import CITO_NS, PROJECT_NS, SCI_NS, canonical_id_from_entity_uri


class EntityFreshnessInfo(TypedDict):
    """Per-entity metadata required by derive_freshness().

    Built by callers (typically materialize_graph) from each project entity,
    keyed in the entities dict by the entity's URI string.
    """
    kind_class: EntityClass
    last_reviewed: date | None
    created: date | None
    updated: date | None
    review_horizon_days: int | None


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


def close_bears_on(
    dataset: Dataset,
    *,
    kind_class: dict[str, EntityClass],
) -> None:
    """Emit transitive `bears_on` edges via DFS with cycle protection.

    For each source S that has any outgoing `bears_on` edge, walk the chain
    forward; whenever a reachable node is epistemic, emit `S bears_on T`.
    Skip self-edges (cycles through operational hops produce them otherwise).

    `kind_class` is required. Unclassified nodes are treated as non-epistemic —
    they are traversed during DFS but never emitted as closure targets. This
    matches the design doc's "default to operational" stance for unclassified
    extension kinds.
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    # Build adjacency map from existing bears_on edges.
    adjacency: dict[URIRef, set[URIRef]] = {}
    for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None)):
        adjacency.setdefault(s, set()).add(o)

    new_triples: set[tuple[URIRef, URIRef, URIRef]] = set()
    for source in list(adjacency):
        # DFS from source.
        stack: list[URIRef] = list(adjacency[source])
        visited: set[URIRef] = set()
        while stack:
            node = stack.pop()
            if node in visited or node == source:
                continue
            visited.add(node)
            if kind_class.get(str(node)) == EntityClass.EPISTEMIC:
                new_triples.add((source, SCI_NS.bearsOn, node))
            stack.extend(adjacency.get(node, set()))

    for triple in new_triples:
        knowledge.add(triple)


def derive_freshness(
    dataset: Dataset,
    *,
    entities: dict[str, EntityFreshnessInfo],
    today: date,
) -> None:
    """Compute EpistemicFreshness for every epistemic entity and emit triples.

    `entities` maps URI string -> dict with keys:
        kind_class: EntityClass
        last_reviewed: date | None
        created: date | None
        updated: date | None
        review_horizon_days: int | None

    Algorithm:
      State precedence (highest first): needs-review > stale > fresh.

      1. For each epistemic entity E:
         a. baseline = E.last_reviewed or E.created
         b. Walk every (S, bears_on, E) triple. For each S, change_at = S.updated or S.created.
         c. If any change_at > baseline, state = "needs-review", upstream_change_at = max(change_at).
            triggered_by = list of all S with change_at > baseline.
         d. Else if review_horizon_days set and (today - baseline).days > horizon, state = "stale".
         e. Else state = "fresh".
      2. Emit:
         (E, sci:freshnessState, Literal(state))
         (E, sci:upstreamChangeAt, Literal(date, datatype=xsd:date))   if upstream_change_at
         (E, sci:triggeredBy, S)                                       for each S in triggered_by

    Skips non-epistemic entities silently (no triples emitted).
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    # Build inverse adjacency: target -> {sources that bear on it}.
    bears_on_in: dict[URIRef, set[URIRef]] = {}
    for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None)):
        bears_on_in.setdefault(o, set()).add(s)

    for entity_uri_str, info in entities.items():
        if info["kind_class"] != EntityClass.EPISTEMIC:
            continue
        entity_uri = URIRef(entity_uri_str)
        baseline = info.get("last_reviewed") or info.get("created")
        if baseline is None:
            # An entity with neither last_reviewed nor created has no defensible
            # baseline. Surface the inconsistency rather than masking it as fresh —
            # downstream consumers (entity needs-review, science:status) will then
            # see the entity flagged for human attention.
            knowledge.add((entity_uri, SCI_NS.freshnessState, Literal("needs-review")))
            knowledge.add((
                entity_uri,
                SCI_NS.triggeredBy,
                Literal("missing-baseline: no last_reviewed or created date"),
            ))
            continue

        triggered: list[URIRef] = []
        upstream_change_at: date | None = None
        for source_uri in bears_on_in.get(entity_uri, set()):
            source_info = entities.get(str(source_uri))
            if source_info is None:
                continue
            change_at = source_info.get("updated") or source_info.get("created")
            if change_at is None:
                continue
            if change_at > baseline:
                triggered.append(source_uri)
                if upstream_change_at is None or change_at > upstream_change_at:
                    upstream_change_at = change_at

        if triggered:
            state = "needs-review"
        else:
            horizon = info.get("review_horizon_days")
            if horizon is not None and (today - baseline).days > horizon:
                state = "stale"
            else:
                state = "fresh"

        knowledge.add((entity_uri, SCI_NS.freshnessState, Literal(state)))
        if upstream_change_at is not None:
            knowledge.add((
                entity_uri,
                SCI_NS.upstreamChangeAt,
                Literal(upstream_change_at.isoformat(), datatype=XSD.date),
            ))
        for source_uri in sorted(triggered):
            knowledge.add((entity_uri, SCI_NS.triggeredBy, source_uri))


def propagate_freshness_in_memory(project_root: Path) -> list[dict]:
    """Compute freshness without writing the materialized graph.

    Same audit gate as `materialize_graph`: raises ValueError if any
    source_refs / evidence_refs / typed-relation reference is unresolved.
    Without this, a project with broken refs would silently produce an
    incomplete freshness picture.

    Returns rows of {"id": "<canonical_id>", "kind": "<kind>", "state": "<state>"}.
    """
    # Lazy imports to avoid cycle.
    from science_tool.graph.materialize import _build_dataset_from_sources
    from science_tool.graph.migrate import audit_project_sources

    sources = load_project_sources(project_root.resolve())
    rows, has_failures = audit_project_sources(sources)
    if has_failures:
        details = "; ".join(f"{row['source']} -> {row['target']}" for row in rows if row["status"] == "fail")
        raise ValueError(f"Cannot compute freshness with unresolved references: {details}")

    dataset = _build_dataset_from_sources(sources)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    rows: list[dict] = []
    for s, _, o in knowledge.triples((None, SCI_NS.freshnessState, None)):
        state = str(o)
        if state == "fresh":
            continue
        canonical_id = canonical_id_from_entity_uri(str(s))
        if canonical_id is None:
            continue
        kind, _, _ = canonical_id.partition(":")
        rows.append({"id": canonical_id, "kind": kind, "state": state})
    rows.sort(key=lambda r: (r["state"], r["kind"], r["id"]))
    return rows
