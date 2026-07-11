from __future__ import annotations

from collections import deque
from pathlib import Path

from rdflib import URIRef
from rdflib.namespace import PROV, RDF, SKOS

from ...instruments import InstrumentResult
from .constants import CITO_NS, SCHEMA_NS, SCI_NS
from .dataset import _load_dataset
from .evidence_signals import _linked_claims_for_hypothesis, _source_strings
from .identity import (
    _about_tokens,
    _graph_uri,
    _resolve_center_entity,
    _short_name,
    entity_in_graph,
)


def query_neighborhood(
    graph_path: Path,
    center: str,
    hops: int,
    graph_layer: str,
    limit: int,
) -> InstrumentResult[dict[str, str]]:
    """Neighbours of ``center`` within ``hops``.

    ``unwired`` when ``center`` is not in the layer. ``_resolve_center_entity`` mints
    a URIRef from any string without consulting the graph, so a typo previously
    produced an empty neighbourhood -- reported as "this entity is isolated".
    """
    dataset = _load_dataset(graph_path)
    layer = dataset.graph(_graph_uri(graph_layer))

    center_uri = _resolve_center_entity(center)
    if not entity_in_graph(center_uri, layer):
        return InstrumentResult.unwired(
            code="center_not_in_graph",
            reason=f"{center!r} does not exist in graph layer {graph_layer!r}.",
        )

    adjacency: dict[URIRef, set[URIRef]] = {}
    triples: list[tuple[URIRef, URIRef, URIRef]] = []

    for subj, pred, obj in layer:
        if not isinstance(subj, URIRef) or not isinstance(pred, URIRef) or not isinstance(obj, URIRef):
            continue
        triples.append((subj, pred, obj))
        adjacency.setdefault(subj, set()).add(obj)
        adjacency.setdefault(obj, set()).add(subj)

    visited: set[URIRef] = {center_uri}
    queue: deque[tuple[URIRef, int]] = deque([(center_uri, 0)])
    while queue:
        node, depth = queue.popleft()
        if depth >= hops:
            continue
        for neighbor in adjacency.get(node, set()):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, depth + 1))

    rows: list[dict[str, str]] = []
    for subj, pred, obj in triples:
        if subj in visited or obj in visited:
            rows.append(
                {
                    "subject": str(subj),
                    "predicate": str(pred),
                    "object": str(obj),
                }
            )
    return InstrumentResult.from_rows(rows[:limit])


def query_claims(graph_path: Path, about: str, limit: int) -> InstrumentResult[dict[str, str]]:
    """Claims whose text matches ``about``.

    No unwired state: ``about`` is a free-text SEARCH TERM, not an identifier, so
    "no match" is a real answer. Inventing an unwired here would be as dishonest
    as the spurious empty this migration exists to remove.
    """
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    tokens = _about_tokens(about)
    rows: list[dict[str, str]] = []
    for prop_uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Proposition)):
        text_obj = next(knowledge.objects(prop_uri, SCHEMA_NS.text), None)
        if text_obj is None:
            continue
        text = str(text_obj)
        if not any(token in text.lower() for token in tokens):
            continue

        sources = sorted({str(src) for src in provenance.objects(prop_uri, PROV.wasDerivedFrom)})
        rows.append(
            {
                "claim": str(prop_uri),
                "text": text,
                "sources": "; ".join(sources),
            }
        )
    return InstrumentResult.from_rows(rows[:limit])


def query_evidence(
    graph_path: Path,
    target_ref: str,
    limit: int,
) -> InstrumentResult[dict[str, str]]:
    """Evidence for/against ``target_ref``.

    ``unwired`` when the target is not in the graph. Previously a typo'd claim id
    resolved to a valid-looking URI, matched nothing, and the command reported that
    the claim had NO SUPPORTING OR DISPUTING EVIDENCE -- an affirmative statement
    about the literature, manufactured from a misspelling.
    """
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    target_uri = _resolve_center_entity(target_ref)
    if not entity_in_graph(target_uri, knowledge):
        return InstrumentResult.unwired(
            code="target_not_in_graph",
            reason=f"{target_ref!r} does not exist in the knowledge graph.",
        )

    rows: list[dict[str, str]] = []
    seen: dict[tuple[str, str], dict[str, str]] = {}

    if (target_uri, RDF.type, SCI_NS.Hypothesis) in knowledge:
        _append_evidence_rows(
            rows=rows,
            seen=seen,
            knowledge=knowledge,
            provenance=provenance,
            target_uri=target_uri,
        )
        for claim_uri in _linked_claims_for_hypothesis(knowledge, target_uri):
            _append_evidence_rows(
                rows=rows,
                seen=seen,
                knowledge=knowledge,
                provenance=provenance,
                target_uri=claim_uri,
            )
    else:
        _append_evidence_rows(
            rows=rows,
            seen=seen,
            knowledge=knowledge,
            provenance=provenance,
            target_uri=target_uri,
        )

    return InstrumentResult.from_rows(rows[:limit])


def _append_evidence_rows(
    rows: list[dict[str, str]],
    seen: dict[tuple[str, str], dict[str, str]],
    knowledge,
    provenance,
    target_uri: URIRef,
) -> None:
    allowed_predicates: tuple[tuple[URIRef, str], ...] = (
        (CITO_NS.supports, "supports"),
        (CITO_NS.disputes, "disputes"),
    )

    for predicate_uri, relation in allowed_predicates:
        for subj, _, _ in knowledge.triples((None, predicate_uri, target_uri)):
            if isinstance(subj, URIRef):
                _append_row(
                    rows=rows,
                    seen=seen,
                    knowledge=knowledge,
                    provenance=provenance,
                    evidence_uri=subj,
                    relation=relation,
                )


def _append_row(
    rows: list[dict[str, str]],
    seen: dict[tuple[str, str], dict[str, str]],
    knowledge,
    provenance,
    evidence_uri: URIRef,
    relation: str,
    fallback_uri: URIRef | None = None,
) -> None:
    key = (str(evidence_uri), relation)
    text_obj = (
        next(knowledge.objects(evidence_uri, SCHEMA_NS.text), None)
        or next(knowledge.objects(evidence_uri, SCHEMA_NS.description), None)
        or next(knowledge.objects(evidence_uri, SKOS.prefLabel), None)
    )
    text = str(text_obj) if text_obj else _short_name(str(evidence_uri))

    sources = _source_strings(provenance, evidence_uri, fallback_uri)
    if fallback_uri is not None and not text:
        fallback_text_obj = next(knowledge.objects(fallback_uri, SCHEMA_NS.text), None)
        text = str(fallback_text_obj) if fallback_text_obj else text

    existing_row = seen.get(key)
    if existing_row is not None:
        existing_sources = {source for source in existing_row["sources"].split("; ") if source}
        existing_sources.update(sources)
        existing_row["sources"] = "; ".join(sorted(existing_sources))
        if not existing_row["text"] and text:
            existing_row["text"] = text
        return

    row = {
        "evidence": str(evidence_uri),
        "relation": relation,
        "text": text,
        "sources": "; ".join(sources),
    }
    rows.append(row)
    seen[key] = row
