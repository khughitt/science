from __future__ import annotations

import hashlib
import re

import click
from rdflib import URIRef
from rdflib.namespace import RDF

from .constants import (
    CURIE_PREFIXES,
    PROJECT_ENTITY_PREFIX_KINDS,
    PROJECT_NS,
    SCI_NS,
)


def _entity_kind_from_uri(uri: URIRef) -> str | None:
    """Extract the project entity kind (e.g. 'proposition', 'question') from a URI.

    Returns None when the URI is not a project-namespaced entity URI — in that
    case the caller should skip kind-based validation.
    """
    raw = str(uri)
    if not raw.startswith(str(PROJECT_NS)):
        return None
    suffix = raw[len(str(PROJECT_NS)) :]
    head = suffix.split("/", 1)[0]
    return PROJECT_ENTITY_PREFIX_KINDS.get(head)


def canonical_id_from_entity_uri(uri: str) -> str | None:
    """Recover an entity canonical_id (e.g. "hypothesis:h1") from its project URI.

    Inverse of `_entity_uri` in materialize.py: PROJECT_NS["hypothesis/h1"] -> "hypothesis:h1".
    Returns None if the URI doesn't match the project-entity shape (e.g. external CURIEs,
    layer URIs, source URIs).
    """
    prefix = str(PROJECT_NS)
    if not uri.startswith(prefix):
        return None
    tail = uri[len(prefix) :]
    if "/" not in tail:
        return None
    kind, _, slug = tail.partition("/")
    if not kind or not slug:
        return None
    # Reject layer URIs like "graph/knowledge", "graph/provenance" — they share the
    # PROJECT_NS prefix but aren't entities.
    if kind == "graph":
        return None
    return f"{kind}:{slug}"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _graph_uri(layer: str) -> URIRef:
    return URIRef(PROJECT_NS[layer])


def _derive_relation_claim_text(subject_uri: URIRef, predicate_uri: URIRef, object_uri: URIRef) -> str:
    return (
        f"{_relation_claim_label(subject_uri)} "
        f"{_relation_claim_label(predicate_uri)} "
        f"{_relation_claim_label(object_uri)}"
    )


def _relation_claim_label(uri: URIRef) -> str:
    short = shorten_uri(str(uri))
    if ":" in short:
        short = short.split(":", 1)[1]
    if "/" in short:
        short = short.rsplit("/", 1)[1]
    return short.replace("_", " ")


def _edge_claims(context_graph, subject_uri: URIRef, predicate_uri: URIRef, object_uri: URIRef) -> list[URIRef]:
    claim_uris: set[URIRef] = set()
    for statement_uri in context_graph.subjects(RDF.subject, subject_uri):
        if (statement_uri, RDF.predicate, predicate_uri) not in context_graph:
            continue
        if (statement_uri, RDF.object, object_uri) not in context_graph:
            continue
        for claim_uri in context_graph.objects(statement_uri, SCI_NS.backedByClaim):
            if isinstance(claim_uri, URIRef):
                claim_uris.add(claim_uri)
    return sorted(claim_uris, key=str)


def _edge_statement_uri(
    context_token: str,
    subject_uri: URIRef,
    predicate_uri: URIRef,
    object_uri: URIRef,
) -> URIRef:
    token = hashlib.sha256(f"{context_token}|{subject_uri}|{predicate_uri}|{object_uri}".encode("utf-8")).hexdigest()
    return URIRef(PROJECT_NS[f"edge_statement/{token[:16]}"])


def _resolve_term(value: str) -> URIRef:
    if value.startswith(("http://", "https://")):
        return URIRef(value)

    if ":" in value:
        prefix, suffix = value.split(":", 1)
        namespace = CURIE_PREFIXES.get(prefix)
        if namespace is not None:
            return URIRef(namespace[suffix])
        if prefix in PROJECT_ENTITY_PREFIX_KINDS:
            return URIRef(PROJECT_NS[f"{prefix}/{suffix}"])
        supported_prefixes = sorted([*CURIE_PREFIXES.keys(), *PROJECT_ENTITY_PREFIX_KINDS])
        raise click.ClickException(
            f"Unknown CURIE prefix '{prefix}'. Supported prefixes: {', '.join(supported_prefixes)}"
        )

    # Bare terms with "/" are already structured paths (e.g. concept/brca1) — preserve as-is
    if "/" in value:
        return URIRef(PROJECT_NS[value])
    # Bare terms without structure get slugified (e.g. "Nucleotide Transformer v2" → nucleotide_transformer_v2)
    return URIRef(PROJECT_NS[_slug(value)])


def _resolve_center_entity(value: str) -> URIRef:
    if value.startswith(("http://", "https://")) or ":" in value or "/" in value:
        return _resolve_term(value)
    return URIRef(PROJECT_NS[f"concept/{_slug(value)}"])


def _about_tokens(about: str) -> set[str]:
    tokens: set[str] = set()
    lowered = about.lower()
    tokens.add(lowered)
    slug = _slug(about).replace("_", " ")
    if slug:
        tokens.add(slug)

    if "/" in about:
        tail = about.rsplit("/", 1)[-1].lower().replace("_", " ")
        if tail:
            tokens.add(tail)
    if ":" in about:
        suffix = about.split(":", 1)[1].lower().replace("_", " ")
        if suffix:
            tokens.add(suffix)
    return {token for token in tokens if token}


def shorten_uri(uri: str) -> str:
    """Shorten a full URI to a readable CURIE-like form for display."""
    project_base = str(PROJECT_NS)
    if uri.startswith(project_base):
        return uri[len(project_base) :]
    for prefix, ns in CURIE_PREFIXES.items():
        ns_str = str(ns)
        if uri.startswith(ns_str):
            return f"{prefix}:{uri[len(ns_str) :]}"
    return uri


def _short_name(uri: str) -> str:
    if uri.startswith(str(PROJECT_NS)):
        return uri.replace(str(PROJECT_NS), "")
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rsplit("/", 1)[-1]
