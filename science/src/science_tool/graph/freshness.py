"""Freshness engine — bears_on derivation and EpistemicFreshness computation.

Implements Phase 1 of docs/plans/2026-05-03-epistemic-dependency-graph-design.md.
Operates over an rdflib Dataset that has already been populated with the
project's typed relations and provenance triples by `materialize_graph()`.

Public surface:
    derive_bears_on_from_typed_edges(dataset)
    derive_bears_on_from_chain_links(dataset)
    derive_bears_on_from_audits(dataset)
    derive_bears_on_from_pre_registrations(dataset, *, pre_registration_targets, kind_class)
    derive_bears_on_from_provenance(dataset, *, kind_class)
    derive_bears_on_from_produced_by_code(dataset, *, eligible_code_files)
    close_bears_on(dataset, *, kind_class)
    derive_freshness(dataset, *, entities, today)
"""

from __future__ import annotations

import hashlib
from collections import deque
from datetime import date
from pathlib import Path
from typing import TypedDict

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import PROV, RDF, XSD

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


def _emit_bears_on_edge(knowledge: Graph, source: URIRef, target: URIRef, depth: int) -> None:
    """Emit a reified BearsOnEdge with depth metadata for Phase 2 sampling.

    Each call adds a content-addressed named node carrying (source, target, depth).
    The node URI is derived from a SHA-256 hash of the (source, target, depth)
    tuple, ensuring deterministic and stable identifiers (no blank nodes — the
    canonical graph serializer forbids them).

    Phase 2 queries `MIN(?depth) WHERE { ?bn a sci:BearsOnEdge ; sci:bearsOnSource
    ?s ; sci:bearsOnTarget ?t ; sci:bearsOnDepth ?depth }` to recover the shortest
    path. Direct (depth 1) and closure (depth 2+) edges for the same pair coexist;
    SPARQL MIN is the canonical aggregator.
    """
    key = f"{source}\x00{target}\x00{depth}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    edge_node = URIRef(PROJECT_NS[f"bears-on-edge/{digest}"])
    knowledge.add((edge_node, RDF.type, SCI_NS.BearsOnEdge))
    knowledge.add((edge_node, SCI_NS.bearsOnSource, source))
    knowledge.add((edge_node, SCI_NS.bearsOnTarget, target))
    knowledge.add((edge_node, SCI_NS.bearsOnDepth, Literal(depth, datatype=XSD.integer)))


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
            if not isinstance(s, URIRef) or not isinstance(o, URIRef):
                continue
            knowledge.add((s, SCI_NS.bearsOn, o))
            _emit_bears_on_edge(knowledge, s, o, 1)
    for predicate in inverse_predicates:
        for s, _, o in knowledge.triples((None, predicate, None)):
            if not isinstance(s, URIRef) or not isinstance(o, URIRef):
                continue
            knowledge.add((o, SCI_NS.bearsOn, s))
            _emit_bears_on_edge(knowledge, o, s, 1)

    # has_participant: emit only when participant is itself epistemic.
    for s, _, o in knowledge.triples((None, SCI_NS.hasParticipant, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        if kind_class.get(str(o)) == EntityClass.EPISTEMIC:
            knowledge.add((o, SCI_NS.bearsOn, s))
            _emit_bears_on_edge(knowledge, o, s, 1)


def derive_bears_on_from_chain_links(dataset: Dataset) -> None:
    """Emit `bears_on` triples from sci:hasLink (inverse).

    Rule: `?c sci:hasLink ?x` -> `?x bears_on ?c` (chain link bears on its chain).

    Source kind discipline (chain must be a structural-chain) is enforced at
    materialize-time by `relation_allows_kinds`; this deriver assumes any
    `sci:hasLink` triple already passed validation.
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for s, _, o in knowledge.triples((None, SCI_NS.hasLink, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        knowledge.add((o, SCI_NS.bearsOn, s))
        _emit_bears_on_edge(knowledge, o, s, 1)


def derive_bears_on_from_audits(dataset: Dataset) -> None:
    """Emit `bears_on` triples from sci:audits.

    Rule: `?a sci:audits ?c` -> `?c bears_on ?a` (chain bears on the audit
    that asserts a verdict over it). Mirrors the `tests` predicate's shape.
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for s, _, o in knowledge.triples((None, SCI_NS.audits, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        knowledge.add((o, SCI_NS.bearsOn, s))
        _emit_bears_on_edge(knowledge, o, s, 1)


def derive_bears_on_from_pre_registrations(
    dataset: Dataset,
    *,
    pre_registration_targets: dict[URIRef, list[URIRef]],
    kind_class: dict[str, EntityClass],
) -> None:
    """Emit pre-registration `bears_on` edges to epistemic commitment targets.

    `pre_registration_targets` is built from source frontmatter by the
    materializer so this deriver can distinguish absent `commits_to` from an
    explicit empty list. Only epistemic targets are valid `bears_on` sinks.
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for pre_registration_uri, targets in pre_registration_targets.items():
        for target_uri in targets:
            if kind_class.get(str(target_uri)) != EntityClass.EPISTEMIC:
                continue
            knowledge.add((pre_registration_uri, SCI_NS.bearsOn, target_uri))
            _emit_bears_on_edge(knowledge, pre_registration_uri, target_uri, 1)


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
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        # In materialize.py the *derived* side is the subject of wasDerivedFrom.
        # If the derived entity is epistemic, the source bears on it.
        if kind_class.get(str(s)) == EntityClass.EPISTEMIC:
            knowledge.add((o, SCI_NS.bearsOn, s))
            _emit_bears_on_edge(knowledge, o, s, 1)


def derive_bears_on_from_produced_by_code(
    dataset: Dataset,
    *,
    eligible_code_files: set[URIRef],
) -> None:
    """Emit `bears_on` from `sci:producedBy` code edges (Plan C).

    Rule: `?dataset sci:producedBy ?code_file` -> `?code_file bears_on ?dataset`,
    only when `?code_file` is propagation-eligible (decision-bearing, fail-closed;
    set built by the materializer). Operational data artifacts are valid direct
    bears_on conduit targets; `close_bears_on` walks through them to epistemic
    findings.
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for dataset_uri, _, code_uri in knowledge.triples((None, SCI_NS.producedBy, None)):
        if not isinstance(dataset_uri, URIRef) or not isinstance(code_uri, URIRef):
            continue
        if code_uri not in eligible_code_files:
            continue
        knowledge.add((code_uri, SCI_NS.bearsOn, dataset_uri))
        _emit_bears_on_edge(knowledge, code_uri, dataset_uri, 1)


def close_bears_on(
    dataset: Dataset,
    *,
    kind_class: dict[str, EntityClass],
) -> None:
    """Emit transitive `bears_on` edges via BFS with depth tracking.

    For each source S that has any outgoing `bears_on` edge, walk the chain
    forward via BFS (breadth-first for shortest-path semantics); whenever a
    reachable epistemic node is found at depth ≥ 2, emit `S bears_on T` and
    a BearsOnEdge with the minimum depth across all paths.

    `kind_class` is required. Unclassified nodes are treated as non-epistemic —
    they are traversed during BFS but never emitted as closure targets. This
    matches the design doc's "default to operational" stance for unclassified
    extension kinds.

    Direct (depth-1) edges are not re-emitted by the closure — they are
    already emitted by `derive_bears_on_from_typed_edges` and
    `derive_bears_on_from_provenance`. Phase 2 uses `SELECT MIN(?depth)` over
    all BearsOnEdge nodes for a given (source, target) pair.
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    # Build adjacency map from existing bears_on edges (depth-1 direct ones).
    adjacency: dict[URIRef, set[URIRef]] = {}
    for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None)):
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
        adjacency.setdefault(s, set()).add(o)

    # BFS from each source, starting from grand-neighbors (depth 2) to avoid
    # re-emitting direct edges that are already depth-1 BearsOnEdge nodes.
    new_edges: dict[tuple[URIRef, URIRef], int] = {}
    for source in list(adjacency):
        queue: deque[tuple[URIRef, int]] = deque()
        visited: set[URIRef] = {source}
        for direct_nbr in adjacency[source]:
            visited.add(direct_nbr)
            for grand_nbr in adjacency.get(direct_nbr, set()):
                queue.append((grand_nbr, 2))
        while queue:
            node, depth = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            if kind_class.get(str(node)) == EntityClass.EPISTEMIC:
                key = (source, node)
                if key not in new_edges or depth < new_edges[key]:
                    new_edges[key] = depth
            for nbr in adjacency.get(node, set()):
                queue.append((nbr, depth + 1))

    for (source, target), depth in new_edges.items():
        knowledge.add((source, SCI_NS.bearsOn, target))
        _emit_bears_on_edge(knowledge, source, target, depth)


def derive_freshness(
    dataset: Dataset,
    *,
    entities: dict[str, EntityFreshnessInfo],
    today: date,
    source_changes: dict[str, date],
) -> None:
    """Compute EpistemicFreshness for every epistemic entity and emit triples.

    `entities` maps URI string -> dict with keys:
        kind_class: EntityClass
        last_reviewed: date | None
        created: date | None
        updated: date | None
        review_horizon_days: int | None

    `source_changes` maps a SourceSnapshot node URI (str) to the observed_on of
    its current SourceChange. When an upstream `bears_on` source is a snapshot
    node, that date is used as its change_at — so a content change triggers
    needs-review even when the authored `updated:` date did not move. triggeredBy
    then points to the snapshot node (typed sci:SourceSnapshot in the graph),
    keeping the cause distinguishable from date-driven entity triggers.

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
        if not isinstance(s, URIRef) or not isinstance(o, URIRef):
            continue
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
            knowledge.add(
                (
                    entity_uri,
                    SCI_NS.triggeredBy,
                    Literal("missing-baseline: no last_reviewed or created date"),
                )
            )
            continue

        triggered: list[URIRef] = []
        upstream_change_at: date | None = None
        for source_uri in bears_on_in.get(entity_uri, set()):
            source_key = str(source_uri)
            if source_key in source_changes:
                change_at: date | None = source_changes[source_key]
            else:
                source_info = entities.get(source_key)
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
        # Phase 2 prep: emit last_reviewed when set so sampling can read it
        # from the graph instead of re-parsing markdown frontmatter.
        last_reviewed = info.get("last_reviewed")
        if last_reviewed is not None:
            knowledge.add(
                (
                    entity_uri,
                    SCI_NS.lastReviewed,
                    Literal(last_reviewed.isoformat(), datatype=XSD.date),
                )
            )
        if upstream_change_at is not None:
            knowledge.add(
                (
                    entity_uri,
                    SCI_NS.upstreamChangeAt,
                    Literal(upstream_change_at.isoformat(), datatype=XSD.date),
                )
            )
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

    sources = load_project_sources(project_root.resolve(), strict_identity=False)
    audit_rows, has_failures = audit_project_sources(sources)
    if has_failures:
        details = "; ".join(f"{row['source']} -> {row['target']}" for row in audit_rows if row["status"] == "fail")
        raise ValueError(f"Cannot compute freshness with unresolved references: {details}")

    if not sources.freshness_enabled:
        return []

    # Lazy imports avoid the freshness -> source_snapshots -> freshness import cycle
    # (source_snapshots imports _emit_bears_on_edge from this module).
    from science_tool.graph.source_snapshots import compute_source_snapshots
    from science_tool.graph.store import DEFAULT_GRAPH_PATH

    prior_graph_path = project_root.resolve() / DEFAULT_GRAPH_PATH
    snapshots = compute_source_snapshots(sources, prior_graph_path=prior_graph_path, today=date.today())
    dataset = _build_dataset_from_sources(sources, source_snapshots=snapshots)
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
