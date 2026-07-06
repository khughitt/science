from __future__ import annotations

import hashlib
from pathlib import Path

import click
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, SKOS

from .constants import PROJECT_NS, SCHEMA_NS, SCI_NS
from .dataset import _load_dataset, _save_dataset
from .identity import _graph_uri, _resolve_term, _slug


def add_article(graph_path: Path, doi: str) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    doi_slug = _slug(doi)
    article_uri = URIRef(PROJECT_NS[f"article/doi_{doi_slug}"])
    knowledge.add((article_uri, RDF.type, SCI_NS.Article))
    knowledge.add((article_uri, SCHEMA_NS.identifier, Literal(doi)))

    _save_dataset(dataset, graph_path)
    return article_uri


def add_falsification(
    graph_path: Path,
    predicted: str,
    source_of_prediction: str,
    observed: str,
    decision: str,
    proposition_ref: str,
    falsification_id: str | None = None,
    supersedes_claim: str | None = None,
) -> URIRef:
    """Add a falsification record linked to a proposition-backed claim."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if falsification_id is not None:
        token = _slug(falsification_id)
        if not token:
            raise click.ClickException("Falsification ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{predicted}|{observed}|{decision}".encode("utf-8")).hexdigest()[:12]

    proposition_uri = _resolve_term(proposition_ref)
    if (proposition_uri, RDF.type, SCI_NS.Proposition) not in knowledge:
        raise click.ClickException(f"Falsification target '{proposition_ref}' must resolve to a proposition entity")

    falsification_uri = URIRef(PROJECT_NS[f"falsification/{token}"])
    knowledge.add((falsification_uri, RDF.type, SCI_NS.Falsification))
    knowledge.add((falsification_uri, SCI_NS.predicted, Literal(predicted)))
    knowledge.add((falsification_uri, SCI_NS.observed, Literal(observed)))
    knowledge.add((falsification_uri, SCI_NS.decision, Literal(decision)))
    knowledge.add((falsification_uri, SCI_NS.sourceOfPrediction, Literal(source_of_prediction)))
    knowledge.add((falsification_uri, SCI_NS.falsifies, proposition_uri))
    if supersedes_claim:
        knowledge.add((falsification_uri, SCI_NS.supersedesClaim, _resolve_term(supersedes_claim)))

    _save_dataset(dataset, graph_path)
    return falsification_uri


def add_story(
    graph_path: Path,
    title: str,
    summary: str,
    about: str,
    interpretations: list[str],
    status: str = "draft",
    story_id: str | None = None,
) -> URIRef:
    """Add a story — a narrative arc synthesizing interpretations around a question or hypothesis."""
    if status not in ("draft", "developing", "mature"):
        raise click.ClickException(f"Story status must be draft/developing/mature, got '{status}'")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if story_id is not None:
        token = _slug(story_id)
        if not token:
            raise click.ClickException("Story ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{title}".encode("utf-8")).hexdigest()[:12]

    story_uri = URIRef(PROJECT_NS[f"story/{token}"])
    knowledge.add((story_uri, RDF.type, SCI_NS.Story))
    knowledge.add((story_uri, SKOS.prefLabel, Literal(title)))
    knowledge.add((story_uri, SCHEMA_NS.description, Literal(summary)))
    knowledge.add((story_uri, SCI_NS.projectStatus, Literal(status)))
    knowledge.add((story_uri, SCI_NS.organizedBy, _resolve_term(about)))

    for interp_ref in interpretations:
        knowledge.add((story_uri, SCI_NS.synthesizes, _resolve_term(interp_ref)))

    _save_dataset(dataset, graph_path)
    return story_uri
