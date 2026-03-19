from __future__ import annotations

import hashlib
import importlib.resources
import json
import re
import subprocess
from collections import deque
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import NotRequired, TypedDict, cast

import click
from rdflib import Dataset, Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF, SKOS, XSD

DEFAULT_GRAPH_PATH = Path("knowledge/graph.trig")
PROJECT_NS = Namespace("http://example.org/project/")
SCI_NS = Namespace("http://example.org/science/vocab/")
SCIC_NS = Namespace("http://example.org/science/vocab/causal/")
SCHEMA_NS = Namespace("https://schema.org/")
BIOLINK_NS = Namespace("https://w3id.org/biolink/vocab/")
CITO_NS = Namespace("http://purl.org/spar/cito/")
DCTERMS_NS = Namespace("http://purl.org/dc/terms/")
REVISION_URI = URIRef(PROJECT_NS["graph_revision"])


class InquiryEdge(TypedDict):
    subject: str
    predicate: str
    object: str
    claims: NotRequired[list[str]]


class InquiryInfo(TypedDict):
    slug: str
    label: str
    status: str
    inquiry_type: str
    target: str
    created: str
    description: str
    treatment: str | None
    outcome: str | None
    boundary_in: list[str]
    boundary_out: list[str]
    edges: list[InquiryEdge]


class ClaimSummaryData(TypedDict):
    uri: URIRef
    claim: str
    label: str
    text: str
    belief_state: str
    support_count: int
    dispute_count: int
    source_count: int
    evidence_types: list[str]
    has_empirical_data: bool
    signals: list[str]
    risk_score: float


class NeighborhoodSummaryData(TypedDict):
    center_uri: URIRef
    label: str
    text: str
    neighbor_claim_count: int
    avg_risk_score: float
    contested_count: int
    single_source_count: int
    no_empirical_count: int
    structural_fragility: str
    neighborhood_risk: float


class QuestionSummaryData(TypedDict):
    uri: URIRef
    question: str
    label: str
    text: str
    claim_count: int
    neighborhood_count: int
    avg_risk_score: float
    contested_claim_count: int
    single_source_claim_count: int
    no_empirical_claim_count: int
    priority_score: float


class InquirySummaryData(TypedDict):
    uri: URIRef
    inquiry: str
    label: str
    inquiry_type: str
    status: str
    claim_count: int
    backed_claim_count: int
    avg_risk_score: float
    contested_claim_count: int
    single_source_claim_count: int
    no_empirical_claim_count: int
    priority_score: float

VALID_INQUIRY_TYPES: tuple[str, ...] = ("general", "causal")

GRAPH_LAYERS: tuple[str, ...] = (
    "graph/knowledge",
    "graph/bridge",
    "graph/causal",
    "graph/provenance",
    "graph/datasets",
)

CURIE_PREFIXES: dict[str, Namespace] = {
    "sci": SCI_NS,
    "scic": SCIC_NS,
    "schema": SCHEMA_NS,
    "prov": Namespace(str(PROV)),
    "skos": Namespace(str(SKOS)),
    "rdf": Namespace(str(RDF)),
    "biolink": BIOLINK_NS,
    "cito": CITO_NS,
    "dcterms": DCTERMS_NS,
}
PROJECT_ENTITY_PREFIXES: set[str] = {
    "paper",
    "concept",
    "claim",
    "relation_claim",
    "hypothesis",
    "dataset",
    "question",
    "evidence",
    "inquiry",
    "task",
}
RELATION_CLAIM_PREDICATE_URIS: frozenset[URIRef] = frozenset(
    {
        SCI_NS.relatedTo,
        SCIC_NS.causes,
        SCIC_NS.confounds,
        CITO_NS.supports,
        CITO_NS.disputes,
        CITO_NS.discusses,
    }
)

INITIAL_GRAPH_TEMPLATE = """@prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:   <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:   <http://www.w3.org/2004/02/skos/core#> .
@prefix prov:   <http://www.w3.org/ns/prov#> .
@prefix schema: <https://schema.org/> .
@prefix sci:    <http://example.org/science/vocab/> .
@prefix scic:   <http://example.org/science/vocab/causal/> .
@prefix :       <http://example.org/project/> .

<http://example.org/project/graph/knowledge> {
}

<http://example.org/project/graph/bridge> {
}

<http://example.org/project/graph/causal> {
}

<http://example.org/project/graph/provenance> {
}

<http://example.org/project/graph/datasets> {
}
"""


def init_graph_file(graph_path: Path) -> None:
    if graph_path.exists():
        raise click.ClickException(f"Graph file already exists: {graph_path}")

    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")

    project_root = _project_root_from_graph_path(graph_path)
    _copy_viz_notebook(project_root / "code" / "notebooks")


def read_graph_stats(graph_path: Path) -> dict[str, int]:
    dataset = _load_dataset(graph_path)

    stats: dict[str, int] = {}
    for layer in GRAPH_LAYERS:
        stats[layer] = len(dataset.graph(_graph_uri(layer)))

    return stats


def add_concept(
    graph_path: Path,
    label: str,
    concept_type: str | None,
    ontology_id: str | None,
    note: str | None = None,
    definition: str | None = None,
    properties: list[tuple[str, str]] | None = None,
    status: str | None = None,
    source: str | None = None,
) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    concept_uri = URIRef(PROJECT_NS[f"concept/{_slug(label)}"])
    knowledge.add((concept_uri, RDF.type, SCI_NS.Concept))
    knowledge.add((concept_uri, SKOS.prefLabel, Literal(label)))

    if concept_type:
        knowledge.add((concept_uri, RDF.type, _resolve_term(concept_type)))
    if ontology_id:
        knowledge.add((concept_uri, SCHEMA_NS.identifier, Literal(ontology_id)))
    if note:
        knowledge.add((concept_uri, SKOS.note, Literal(note)))
    if definition:
        knowledge.add((concept_uri, SKOS.definition, Literal(definition)))
    if properties:
        for key, value in properties:
            pred = _resolve_term(key) if ":" in key else SCI_NS[key]
            knowledge.add((concept_uri, pred, Literal(value)))
    if status:
        knowledge.add((concept_uri, SCI_NS.projectStatus, Literal(status)))
    if source:
        provenance = dataset.graph(_graph_uri("graph/provenance"))
        provenance.add((concept_uri, PROV.wasDerivedFrom, _resolve_term(source)))

    _save_dataset(dataset, graph_path)
    return concept_uri


def add_paper(graph_path: Path, doi: str) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    doi_slug = _slug(doi)
    paper_uri = URIRef(PROJECT_NS[f"paper/doi_{doi_slug}"])
    knowledge.add((paper_uri, RDF.type, SCI_NS.Paper))
    knowledge.add((paper_uri, SCHEMA_NS.identifier, Literal(doi)))

    _save_dataset(dataset, graph_path)
    return paper_uri


def add_claim(
    graph_path: Path,
    text: str,
    source: str,
    confidence: float | None,
    evidence_type: str | None = None,
    claim_id: str | None = None,
) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    if claim_id is not None:
        token = _slug(claim_id)
        if not token:
            raise click.ClickException("Claim ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{source}|{text}".encode("utf-8")).hexdigest()[:12]

    claim_uri = URIRef(PROJECT_NS[f"claim/{token}"])
    knowledge.add((claim_uri, RDF.type, SCI_NS.Claim))
    knowledge.add((claim_uri, SCHEMA_NS.text, Literal(text)))

    provenance.add((claim_uri, PROV.wasDerivedFrom, _resolve_term(source)))
    if confidence is not None:
        provenance.add((claim_uri, SCI_NS.confidence, Literal(confidence, datatype=XSD.decimal)))
    if evidence_type is not None:
        provenance.add((claim_uri, SCI_NS.evidenceType, Literal(evidence_type)))

    _save_dataset(dataset, graph_path)
    return claim_uri


def add_relation_claim(
    graph_path: Path,
    subject: str,
    predicate: str,
    obj: str,
    source: str,
    confidence: float | None,
    evidence_type: str | None = None,
    text: str | None = None,
    claim_id: str | None = None,
) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    if claim_id is not None:
        token = _slug(claim_id)
        if not token:
            raise click.ClickException("Claim ID must contain at least one alphanumeric character")
    else:
        token = hashlib.sha1(f"{subject}|{predicate}|{obj}|{source}".encode("utf-8")).hexdigest()[:12]

    claim_uri = URIRef(PROJECT_NS[f"relation_claim/{token}"])
    subject_uri = _resolve_term(subject)
    predicate_uri = _resolve_term(predicate)
    object_uri = _resolve_term(obj)
    claim_text = text or _derive_relation_claim_text(subject_uri, predicate_uri, object_uri)

    knowledge.add((claim_uri, RDF.type, SCI_NS.Claim))
    knowledge.add((claim_uri, RDF.type, SCI_NS.RelationClaim))
    knowledge.add((claim_uri, SCHEMA_NS.text, Literal(claim_text)))
    knowledge.add((claim_uri, SCI_NS.claimSubject, subject_uri))
    knowledge.add((claim_uri, SCI_NS.claimPredicate, predicate_uri))
    knowledge.add((claim_uri, SCI_NS.claimObject, object_uri))

    provenance.add((claim_uri, PROV.wasDerivedFrom, _resolve_term(source)))
    if confidence is not None:
        provenance.add((claim_uri, SCI_NS.confidence, Literal(confidence, datatype=XSD.decimal)))
    if evidence_type is not None:
        provenance.add((claim_uri, SCI_NS.evidenceType, Literal(evidence_type)))

    _save_dataset(dataset, graph_path)
    return claim_uri


def add_hypothesis(graph_path: Path, hypothesis_id: str, text: str, source: str, status: str | None = None) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    hypothesis_uri = URIRef(PROJECT_NS[f"hypothesis/{hypothesis_id.lower()}"])
    knowledge.add((hypothesis_uri, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((hypothesis_uri, SCHEMA_NS.identifier, Literal(hypothesis_id)))
    knowledge.add((hypothesis_uri, SCHEMA_NS.text, Literal(text)))

    if status:
        knowledge.add((hypothesis_uri, SCI_NS.projectStatus, Literal(status)))

    provenance.add((hypothesis_uri, PROV.wasDerivedFrom, _resolve_term(source)))

    _save_dataset(dataset, graph_path)
    return hypothesis_uri


def add_question(
    graph_path: Path,
    question_id: str,
    text: str,
    source: str,
    maturity: str = "open",
    status: str | None = None,
    related_hypotheses: list[str] | None = None,
) -> URIRef:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    question_uri = URIRef(PROJECT_NS[f"question/{question_id.lower()}"])
    knowledge.add((question_uri, RDF.type, SCI_NS.Question))
    knowledge.add((question_uri, SCHEMA_NS.identifier, Literal(question_id)))
    knowledge.add((question_uri, SCHEMA_NS.text, Literal(text)))
    knowledge.add((question_uri, SCI_NS.maturity, Literal(maturity)))

    if status:
        knowledge.add((question_uri, SCI_NS.projectStatus, Literal(status)))

    provenance.add((question_uri, PROV.wasDerivedFrom, _resolve_term(source)))

    if related_hypotheses:
        for hyp_ref in related_hypotheses:
            knowledge.add((question_uri, SKOS.related, _resolve_term(hyp_ref)))

    _save_dataset(dataset, graph_path)
    return question_uri


def add_edge(
    graph_path: Path,
    subject: str,
    predicate: str,
    obj: str,
    graph_layer: str,
    claim_refs: list[str] | None = None,
) -> tuple[URIRef, URIRef, URIRef]:
    if graph_layer not in GRAPH_LAYERS:
        raise click.ClickException(f"Unsupported graph layer: {graph_layer}")

    dataset = _load_dataset(graph_path)

    s_uri = _resolve_term(subject)
    p_uri = _resolve_term(predicate)
    o_uri = _resolve_term(obj)

    if graph_layer == "graph/knowledge" and p_uri in RELATION_CLAIM_PREDICATE_URIS:
        raise click.ClickException(
            f"Predicate '{predicate}' is an uncertain scientific assertion; use 'graph add relation-claim' instead."
        )

    # Warn if subject/object URIs don't exist in any graph yet
    for uri, label in [(s_uri, subject), (o_uri, obj)]:
        if not any((uri, None, None) in g for g in dataset.graphs()):
            click.echo(f"Warning: '{label}' resolves to {uri} which is not yet in the graph", err=True)

    layer = dataset.graph(_graph_uri(graph_layer))
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    layer.add((s_uri, p_uri, o_uri))
    if claim_refs:
        _attach_edge_claims(
            context_graph=layer,
            knowledge=knowledge,
            context_token=graph_layer,
            subject_uri=s_uri,
            predicate_uri=p_uri,
            object_uri=o_uri,
            claim_refs=claim_refs,
        )

    _save_dataset(dataset, graph_path)
    return s_uri, p_uri, o_uri


def add_inquiry(
    graph_path: Path,
    slug: str,
    label: str,
    target: str,
    description: str = "",
    status: str = "sketch",
    inquiry_type: str = "general",
) -> URIRef:
    """Create a new inquiry named graph with metadata triples."""
    if inquiry_type not in VALID_INQUIRY_TYPES:
        raise ValueError(f"Invalid inquiry type '{inquiry_type}'. Must be one of: {', '.join(VALID_INQUIRY_TYPES)}")

    safe_slug = _slug(slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    # Duplicate check
    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' already exists")

    inquiry_graph.add((inquiry_uri, RDF.type, SCI_NS.Inquiry))
    inquiry_graph.add((inquiry_uri, SKOS.prefLabel, Literal(label)))
    inquiry_graph.add((inquiry_uri, SCI_NS.inquiryStatus, Literal(status)))
    inquiry_graph.add((inquiry_uri, SCI_NS.inquiryType, Literal(inquiry_type)))
    inquiry_graph.add((inquiry_uri, SCI_NS.target, _resolve_term(target)))

    created = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    inquiry_graph.add((inquiry_uri, DCTERMS_NS.created, Literal(created)))

    if description:
        inquiry_graph.add((inquiry_uri, SKOS.note, Literal(description)))

    _save_dataset(dataset, graph_path)
    return inquiry_uri


def set_boundary_role(
    graph_path: Path,
    inquiry_slug: str,
    entity: str,
    role: str,
) -> None:
    """Assign a boundary role (BoundaryIn or BoundaryOut) to an entity within an inquiry."""
    valid_roles = {"BoundaryIn": SCI_NS.BoundaryIn, "BoundaryOut": SCI_NS.BoundaryOut}
    if role not in valid_roles:
        raise ValueError(f"Invalid boundary role '{role}'. Must be one of: {', '.join(sorted(valid_roles))}")

    safe_slug = _slug(inquiry_slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    entity_uri = _resolve_term(entity)
    inquiry_graph.add((entity_uri, SCI_NS.boundaryRole, valid_roles[role]))

    _save_dataset(dataset, graph_path)


def add_inquiry_node(
    graph_path: Path,
    inquiry_slug: str,
    entity: str,
) -> None:
    """Add an entity as an interior node to an inquiry (no boundary role)."""
    safe_slug = _slug(inquiry_slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    entity_uri = _resolve_term(entity)
    # Mark presence in inquiry by adding its type from knowledge graph
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    for t in knowledge.objects(entity_uri, RDF.type):
        inquiry_graph.add((entity_uri, RDF.type, t))
        break  # one type is sufficient to mark membership
    else:
        # If no type found in knowledge, add a generic membership triple
        inquiry_graph.add((entity_uri, RDF.type, SCI_NS.Concept))

    _save_dataset(dataset, graph_path)


def add_inquiry_edge(
    graph_path: Path,
    inquiry_slug: str,
    subject: str,
    predicate: str,
    obj: str,
    claim_refs: list[str] | None = None,
) -> tuple[URIRef, URIRef, URIRef]:
    """Add a triple to an inquiry's named graph."""
    safe_slug = _slug(inquiry_slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    s_uri = _resolve_term(subject)
    p_uri = _resolve_term(predicate)
    o_uri = _resolve_term(obj)
    inquiry_graph.add((s_uri, p_uri, o_uri))
    if claim_refs:
        _attach_edge_claims(
            context_graph=inquiry_graph,
            knowledge=knowledge,
            context_token=str(inquiry_uri),
            subject_uri=s_uri,
            predicate_uri=p_uri,
            object_uri=o_uri,
            claim_refs=claim_refs,
        )

    _save_dataset(dataset, graph_path)
    return s_uri, p_uri, o_uri


def add_assumption(
    graph_path: Path,
    label: str,
    source: str,
    inquiry_slug: str | None = None,
) -> URIRef:
    """Create an assumption concept in the knowledge layer and optionally link it to an inquiry."""
    uri = add_concept(graph_path, label, concept_type="sci:Assumption", ontology_id=None, source=source)

    # Ensure sci:Assumption type is explicitly present in knowledge layer
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    knowledge.add((uri, RDF.type, SCI_NS.Assumption))

    if inquiry_slug is not None:
        safe_slug = _slug(inquiry_slug)
        inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])
        inquiry_graph = dataset.graph(inquiry_uri)
        if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
            raise ValueError(f"Inquiry '{safe_slug}' does not exist")
        inquiry_graph.add((uri, RDF.type, SCI_NS.Assumption))

    _save_dataset(dataset, graph_path)
    return uri


def add_transformation(
    graph_path: Path,
    label: str,
    inquiry_slug: str,
    tool: str = "",
    params: dict[str, dict[str, str]] | None = None,
) -> URIRef:
    """Create a transformation concept and register it in an inquiry graph."""
    uri = add_concept(graph_path, label, concept_type="sci:Transformation", ontology_id=None)

    safe_slug = _slug(inquiry_slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    inquiry_graph.add((uri, RDF.type, SCI_NS.Transformation))

    if tool:
        inquiry_graph.add((uri, SCI_NS.tool, Literal(tool)))

    if params:
        for _param_name, meta in params.items():
            if "value" in meta:
                inquiry_graph.add((uri, SCI_NS.paramValue, Literal(meta["value"])))
            if "source" in meta:
                inquiry_graph.add((uri, SCI_NS.paramSource, Literal(meta["source"])))
            if "note" in meta:
                inquiry_graph.add((uri, SCI_NS.paramNote, Literal(meta["note"])))
            if "refs" in meta:
                for ref in meta["refs"] if isinstance(meta["refs"], list) else [meta["refs"]]:
                    inquiry_graph.add((uri, SCI_NS.paramRef, Literal(ref)))

    _save_dataset(dataset, graph_path)
    return uri


def set_param_metadata(
    graph_path: Path,
    entity: str,
    value: str,
    source: str,
    refs: list[str] | None = None,
    note: str = "",
) -> None:
    """Attach AnnotatedParam-style metadata (value, source, refs, note) to an entity in the knowledge graph."""
    entity_uri = _resolve_term(entity)

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    knowledge.add((entity_uri, SCI_NS.paramValue, Literal(value)))
    knowledge.add((entity_uri, SCI_NS.paramSource, Literal(source)))

    if note:
        knowledge.add((entity_uri, SCI_NS.paramNote, Literal(note)))

    if refs:
        for ref in refs:
            knowledge.add((entity_uri, SCI_NS.paramRef, Literal(ref)))

    _save_dataset(dataset, graph_path)


def list_inquiries(graph_path: Path) -> list[dict[str, str]]:
    """List all inquiries in the dataset, returning a list of summary dicts."""
    dataset = _load_dataset(graph_path)
    inquiry_prefix = str(PROJECT_NS) + "inquiry/"
    results: list[dict[str, str]] = []

    for ctx in dataset.graphs():
        graph_id = str(ctx.identifier)
        if not graph_id.startswith(inquiry_prefix):
            continue

        slug = graph_id[len(inquiry_prefix) :]
        inquiry_uri = URIRef(graph_id)

        # Only include actual inquiry graphs (must have Inquiry type)
        if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in ctx:
            continue

        label = ""
        status = ""
        target = ""
        created = ""

        for obj in ctx.objects(inquiry_uri, SKOS.prefLabel):
            label = str(obj)
        for obj in ctx.objects(inquiry_uri, SCI_NS.inquiryStatus):
            status = str(obj)
        for obj in ctx.objects(inquiry_uri, SCI_NS.target):
            target = str(obj)
        for obj in ctx.objects(inquiry_uri, DCTERMS_NS.created):
            created = str(obj)

        inquiry_type = ""
        for obj in ctx.objects(inquiry_uri, SCI_NS.inquiryType):
            inquiry_type = str(obj)
        if not inquiry_type:
            inquiry_type = "general"

        results.append(
            {
                "slug": slug,
                "label": label,
                "inquiry_type": inquiry_type,
                "status": status,
                "target": target,
                "created": created,
            }
        )

    return results


def get_inquiry(graph_path: Path, slug: str) -> InquiryInfo:
    """Get detailed information about a specific inquiry, including boundaries and edges."""
    safe_slug = _slug(slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    # Read metadata
    label = str(next(inquiry_graph.objects(inquiry_uri, SKOS.prefLabel), ""))
    status = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryStatus), ""))
    inquiry_type = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryType), "general"))
    target = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.target), ""))
    created = str(next(inquiry_graph.objects(inquiry_uri, DCTERMS_NS.created), ""))
    description = str(next(inquiry_graph.objects(inquiry_uri, SKOS.note), ""))

    # Read treatment/outcome (causal inquiries)
    treatment = next(inquiry_graph.objects(inquiry_uri, SCI_NS.treatment), None)
    outcome = next(inquiry_graph.objects(inquiry_uri, SCI_NS.outcome), None)

    # Collect boundary nodes
    boundary_in: list[str] = []
    boundary_out: list[str] = []
    for s, _p, o in inquiry_graph.triples((None, SCI_NS.boundaryRole, None)):
        if o == SCI_NS.BoundaryIn:
            boundary_in.append(str(s))
        elif o == SCI_NS.BoundaryOut:
            boundary_out.append(str(s))

    # Collect edges (excluding metadata predicates)
    metadata_predicates = {
        RDF.type,
        RDF.subject,
        RDF.predicate,
        RDF.object,
        SKOS.prefLabel,
        SKOS.note,
        SCI_NS.inquiryStatus,
        SCI_NS.inquiryType,
        SCI_NS.target,
        SCI_NS.boundaryRole,
        SCI_NS.treatment,
        SCI_NS.outcome,
        SCI_NS.tool,
        SCI_NS.paramValue,
        SCI_NS.paramSource,
        SCI_NS.paramNote,
        SCI_NS.paramRef,
        SCI_NS.backedByClaim,
        SCI_NS.validatedBy,
        DCTERMS_NS.created,
    }
    edges: list[InquiryEdge] = []
    for s, p, o in inquiry_graph:
        if p not in metadata_predicates:
            edge_info: InquiryEdge = {"subject": str(s), "predicate": str(p), "object": str(o)}
            if isinstance(s, URIRef) and isinstance(p, URIRef) and isinstance(o, URIRef):
                claim_uris = _edge_claims(inquiry_graph, s, p, o)
                if claim_uris:
                    edge_info["claims"] = [str(uri) for uri in claim_uris]
            edges.append(edge_info)

    return {
        "slug": safe_slug,
        "label": label,
        "status": status,
        "inquiry_type": inquiry_type,
        "target": target,
        "created": created,
        "description": description,
        "treatment": str(treatment) if treatment else None,
        "outcome": str(outcome) if outcome else None,
        "boundary_in": boundary_in,
        "boundary_out": boundary_out,
        "edges": edges,
    }


def set_treatment_outcome(
    graph_path: Path,
    inquiry_slug: str,
    treatment: str,
    outcome: str,
) -> None:
    """Set treatment and outcome variables for a causal inquiry."""
    safe_slug = _slug(inquiry_slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    inquiry_type = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryType), "general"))
    if inquiry_type != "causal":
        raise ValueError(f"Treatment/outcome only supported for causal inquiries (got '{inquiry_type}')")

    treatment_uri = _resolve_term(treatment)
    outcome_uri = _resolve_term(outcome)

    # Remove any existing treatment/outcome
    inquiry_graph.remove((inquiry_uri, SCI_NS.treatment, None))
    inquiry_graph.remove((inquiry_uri, SCI_NS.outcome, None))

    inquiry_graph.add((inquiry_uri, SCI_NS.treatment, treatment_uri))
    inquiry_graph.add((inquiry_uri, SCI_NS.outcome, outcome_uri))

    _save_dataset(dataset, graph_path)


def render_inquiry_doc(graph_path: Path, slug: str) -> str:
    """Render an inquiry as a markdown document string.

    Calls get_inquiry() to gather data, then builds a markdown document
    with metadata, boundary node tables, interior nodes, edge list,
    assumptions, and parameters.
    """
    info = get_inquiry(graph_path, slug)
    safe_slug = _slug(slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    # Helper: get label for a URI from knowledge or inquiry graph
    def _label_for(uri_str: str) -> str:
        uri_ref = URIRef(uri_str)
        label = next(knowledge.objects(uri_ref, SKOS.prefLabel), None)
        if label is None:
            label = next(inquiry_graph.objects(uri_ref, SKOS.prefLabel), None)
        return str(label) if label else shorten_uri(uri_str)

    # Helper: get rdf:type for a URI (excluding sci:Concept base type)
    def _type_for(uri_str: str) -> str:
        uri_ref = URIRef(uri_str)
        types: list[str] = []
        for t in knowledge.objects(uri_ref, RDF.type):
            t_str = str(t)
            if t_str != str(SCI_NS.Concept):
                types.append(shorten_uri(t_str))
        for t in inquiry_graph.objects(uri_ref, RDF.type):
            t_str = str(t)
            short = shorten_uri(t_str)
            if t_str != str(SCI_NS.Concept) and short not in types:
                types.append(short)
        return ", ".join(types) if types else ""

    # Helper: get note for a URI
    def _note_for(uri_str: str) -> str:
        uri_ref = URIRef(uri_str)
        note = next(knowledge.objects(uri_ref, SKOS.note), None)
        if note is None:
            note = next(inquiry_graph.objects(uri_ref, SKOS.note), None)
        return str(note) if note else ""

    # Helper: get validatedBy for a URI
    def _validated_by(uri_str: str) -> str:
        uri_ref = URIRef(uri_str)
        vals: list[str] = []
        for v in inquiry_graph.objects(uri_ref, SCI_NS.validatedBy):
            vals.append(shorten_uri(str(v)))
        return ", ".join(vals) if vals else ""

    # Helper: get provenance for a URI
    def _provenance_for(uri_str: str) -> str:
        uri_ref = URIRef(uri_str)
        provenance = dataset.graph(_graph_uri("graph/provenance"))
        sources: list[str] = []
        for src in provenance.objects(uri_ref, PROV.wasDerivedFrom):
            sources.append(shorten_uri(str(src)))
        return ", ".join(sources) if sources else ""

    # Target label
    target_str = info["target"]
    target_id = shorten_uri(target_str)

    # Build boundary sets for interior detection
    boundary_set = set(info["boundary_in"]) | set(info["boundary_out"])

    # Find interior nodes: nodes in edges that are not boundary and not the inquiry itself
    interior_nodes: list[str] = []
    seen: set[str] = set()
    for edge in info["edges"]:
        for uri_str in (edge["subject"], edge["object"]):
            if uri_str not in boundary_set and uri_str not in seen and uri_str != str(inquiry_uri):
                interior_nodes.append(uri_str)
                seen.add(uri_str)

    # Build boundary_in rows
    boundary_in_rows = ""
    for uri_str in info["boundary_in"]:
        name = _label_for(uri_str)
        typ = _type_for(uri_str)
        prov = _provenance_for(uri_str)
        boundary_in_rows += f"| {name} | {typ} | {prov} |\n"

    # Build boundary_out rows
    boundary_out_rows = ""
    for uri_str in info["boundary_out"]:
        name = _label_for(uri_str)
        typ = _type_for(uri_str)
        validation = _validated_by(uri_str)
        boundary_out_rows += f"| {name} | {typ} | {validation} |\n"

    # Build interior rows
    interior_rows = ""
    for uri_str in interior_nodes:
        name = _label_for(uri_str)
        typ = _type_for(uri_str)
        note = _note_for(uri_str)
        interior_rows += f"| {name} | {typ} | {note} |\n"

    # Build edge list
    edge_lines: list[str] = []
    for edge in info["edges"]:
        s = shorten_uri(edge["subject"])
        p = shorten_uri(edge["predicate"])
        o = shorten_uri(edge["object"])
        edge_lines.append(f"- {s} --[{p}]--> {o}")
    edge_list = "\n".join(edge_lines) if edge_lines else "(no edges)"

    # Build assumption rows
    assumption_rows = ""
    for s, _p, _o in inquiry_graph.triples((None, RDF.type, SCI_NS.Assumption)):
        name = _label_for(str(s))
        evidence = _provenance_for(str(s))
        # Also check sci:assumes edges for evidence
        for _s2, _p2, ev in inquiry_graph.triples((s, SCI_NS.assumes, None)):
            ev_label = shorten_uri(str(ev))
            evidence = ev_label if not evidence else f"{evidence}, {ev_label}"
        assumption_rows += f"| {name} | {evidence} |\n"

    # Build param rows
    param_rows = ""
    for s in set(inquiry_graph.subjects(SCI_NS.paramValue, None)):
        name = _label_for(str(s))
        value = str(next(inquiry_graph.objects(s, SCI_NS.paramValue), ""))
        source = str(next(inquiry_graph.objects(s, SCI_NS.paramSource), ""))
        refs_list: list[str] = []
        for r in inquiry_graph.objects(s, SCI_NS.paramRef):
            refs_list.append(str(r))
        refs = ", ".join(refs_list)
        note = str(next(inquiry_graph.objects(s, SCI_NS.paramNote), ""))
        param_rows += f"| {name} | {value} | {source} | {refs} | {note} |\n"

    # Also check knowledge graph for params
    for s_uri_str in list(set([*info["boundary_in"], *info["boundary_out"], *[str(n) for n in interior_nodes]])):
        s_ref = URIRef(s_uri_str)
        val = next(knowledge.objects(s_ref, SCI_NS.paramValue), None)
        if val is not None and s_ref not in set(inquiry_graph.subjects(SCI_NS.paramValue, None)):
            name = _label_for(s_uri_str)
            value = str(val)
            source = str(next(knowledge.objects(s_ref, SCI_NS.paramSource), ""))
            refs_list = []
            for r in knowledge.objects(s_ref, SCI_NS.paramRef):
                refs_list.append(str(r))
            refs = ", ".join(refs_list)
            note = str(next(knowledge.objects(s_ref, SCI_NS.paramNote), ""))
            param_rows += f"| {name} | {value} | {source} | {refs} | {note} |\n"

    # Build unknown rows — check both inquiry graph and knowledge graph
    unknown_rows = ""
    unknown_seen: set[str] = set()
    for s, _p3, _o3 in inquiry_graph.triples((None, RDF.type, SCI_NS.Unknown)):
        uri_str = str(s)
        if uri_str not in unknown_seen:
            unknown_seen.add(uri_str)
            name = _label_for(uri_str)
            note = _note_for(uri_str)
            unknown_rows += f"| {name} | {note} |\n"
    # Also check knowledge graph for Unknown-typed nodes referenced in edges
    all_edge_nodes = set()
    for edge in info["edges"]:
        all_edge_nodes.add(edge["subject"])
        all_edge_nodes.add(edge["object"])
    for node_str in all_edge_nodes:
        if node_str not in unknown_seen and (URIRef(node_str), RDF.type, SCI_NS.Unknown) in knowledge:
            unknown_seen.add(node_str)
            name = _label_for(node_str)
            note = _note_for(node_str)
            unknown_rows += f"| {name} | {note} |\n"

    # Assemble document
    lines = [
        "---",
        f'id: "inquiry:{info["slug"]}"',
        'type: "inquiry"',
        f'title: "{info["label"]}"',
        f'status: "{info["status"]}"',
        "tags: []",
        "source_refs: []",
        "related: []",
        f'created: "{info["created"]}"',
        f'updated: "{info["created"]}"',
        f'target: "{target_id}"',
        "---",
        "",
        f"# Inquiry: {info['label']}",
        "",
        "## Summary",
        "",
        info["description"] or "(no description)",
        "",
        "## Variables",
        "",
        "### Boundary In (Givens)",
        "",
        "| Variable | Type | Provenance |",
        "|---|---|---|",
        boundary_in_rows.rstrip("\n") if boundary_in_rows else "",
        "",
        "### Boundary Out (Produces)",
        "",
        "| Variable | Type | Validation |",
        "|---|---|---|",
        boundary_out_rows.rstrip("\n") if boundary_out_rows else "",
        "",
        "### Interior",
        "",
        "| Variable | Type | Notes |",
        "|---|---|---|",
        interior_rows.rstrip("\n") if interior_rows else "",
        "",
        "## Data Flow",
        "",
        edge_list,
        "",
        "## Assumptions",
        "",
        "| Assumption | Evidence |",
        "|---|---|",
        assumption_rows.rstrip("\n") if assumption_rows else "",
        "",
        "## Unknowns",
        "",
        "| Unknown | Notes |",
        "|---|---|",
        unknown_rows.rstrip("\n") if unknown_rows else "",
        "",
        "## Parameters",
        "",
        "| Parameter | Value | Source | References | Note |",
        "|---|---|---|---|---|",
        param_rows.rstrip("\n") if param_rows else "",
        "",
    ]

    return "\n".join(lines)


def validate_inquiry(graph_path: Path, slug: str) -> list[dict]:
    """Validate an inquiry graph, returning a list of check-result dicts.

    Each result has keys: check (str), status ("pass"/"fail"/"warn"), message (str),
    and optionally details (list).
    """
    safe_slug = _slug(slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    status = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryStatus), "sketch"))
    target = next(inquiry_graph.objects(inquiry_uri, SCI_NS.target), None)

    # Collect boundary nodes
    boundary_in: set[URIRef] = set()
    boundary_out: set[URIRef] = set()
    for s, _p, o in inquiry_graph.triples((None, SCI_NS.boundaryRole, None)):
        if o == SCI_NS.BoundaryIn:
            boundary_in.add(s)
        elif o == SCI_NS.BoundaryOut:
            boundary_out.add(s)

    # Build adjacency from flow edges (feedsInto, produces, and scic:causes for causal inquiries)
    flow_predicates = {SCI_NS.feedsInto, SCI_NS.produces, SCIC_NS.causes}
    adjacency: dict[URIRef, list[URIRef]] = {}
    all_flow_nodes: set[URIRef] = set()
    for s, p, o in inquiry_graph:
        if p in flow_predicates:
            adjacency.setdefault(s, []).append(o)
            all_flow_nodes.add(s)
            all_flow_nodes.add(o)

    results: list[dict] = []

    # 1. boundary_reachability — BFS from BoundaryIn, check all BoundaryOut reachable
    reachable: set[URIRef] = set()
    queue: deque[URIRef] = deque(boundary_in)
    while queue:
        node = queue.popleft()
        if node in reachable:
            continue
        reachable.add(node)
        for neighbor in adjacency.get(node, []):
            if neighbor not in reachable:
                queue.append(neighbor)

    unreachable_out = [str(n) for n in boundary_out if n not in reachable]
    if unreachable_out:
        results.append(
            {
                "check": "boundary_reachability",
                "status": "fail",
                "message": f"{len(unreachable_out)} BoundaryOut node(s) not reachable from any BoundaryIn",
                "details": unreachable_out,
            }
        )
    else:
        results.append(
            {
                "check": "boundary_reachability",
                "status": "pass",
                "message": "All BoundaryOut nodes reachable from BoundaryIn",
            }
        )

    # 2. no_cycles — Kahn's algorithm (topological sort)
    in_degree: dict[URIRef, int] = {n: 0 for n in all_flow_nodes}
    for src, dsts in adjacency.items():
        for dst in dsts:
            in_degree[dst] = in_degree.get(dst, 0) + 1

    topo_queue: deque[URIRef] = deque(n for n, d in in_degree.items() if d == 0)
    sorted_count = 0
    while topo_queue:
        node = topo_queue.popleft()
        sorted_count += 1
        for neighbor in adjacency.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                topo_queue.append(neighbor)

    if sorted_count < len(all_flow_nodes):
        results.append(
            {
                "check": "no_cycles",
                "status": "fail",
                "message": "Cycle detected in flow edges",
            }
        )
    else:
        results.append(
            {
                "check": "no_cycles",
                "status": "pass",
                "message": "No cycles in flow edges",
            }
        )

    # 3. unknown_resolution — find sci:Unknown nodes used in this inquiry
    unknown_nodes: list[str] = []
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    for node in all_flow_nodes:
        if (node, RDF.type, SCI_NS.Unknown) in knowledge or (node, RDF.type, SCI_NS.Unknown) in inquiry_graph:
            unknown_nodes.append(str(node))

    if unknown_nodes and status != "sketch":
        results.append(
            {
                "check": "unknown_resolution",
                "status": "fail",
                "message": f"{len(unknown_nodes)} sci:Unknown node(s) in non-sketch inquiry",
                "details": unknown_nodes,
            }
        )
    else:
        results.append(
            {
                "check": "unknown_resolution",
                "status": "pass",
                "message": "No unresolved Unknown nodes" if not unknown_nodes else "Unknown nodes allowed in sketch",
            }
        )

    # 4. target_exists — check the target has an rdf:type somewhere
    if target is not None:
        has_type = any(True for _ in knowledge.triples((target, RDF.type, None)))
        if not has_type:
            # Also check other graphs
            has_type = any(True for _ in dataset.triples((target, RDF.type, None)))
        if has_type:
            results.append(
                {
                    "check": "target_exists",
                    "status": "pass",
                    "message": "Target node exists",
                }
            )
        else:
            results.append(
                {
                    "check": "target_exists",
                    "status": "fail",
                    "message": f"Target {target} has no rdf:type in the knowledge graph",
                }
            )
    else:
        results.append(
            {
                "check": "target_exists",
                "status": "warn",
                "message": "No target specified for inquiry",
            }
        )

    # 5. orphaned_interior — interior nodes with no incoming or outgoing flow edges
    boundary_all = boundary_in | boundary_out
    orphaned: list[str] = []
    for node in all_flow_nodes:
        if node in boundary_all or node == inquiry_uri:
            continue
        has_incoming = any(node in adjacency.get(src, []) for src in all_flow_nodes)
        has_outgoing = node in adjacency and len(adjacency[node]) > 0
        if not has_incoming or not has_outgoing:
            orphaned.append(str(node))

    if orphaned:
        results.append(
            {
                "check": "orphaned_interior",
                "status": "warn",
                "message": f"{len(orphaned)} interior node(s) missing incoming or outgoing flow edges",
                "details": orphaned,
            }
        )
    else:
        results.append(
            {
                "check": "orphaned_interior",
                "status": "pass",
                "message": "All interior nodes have incoming and outgoing flow edges",
            }
        )

    # === Causal-specific checks (only for type=causal) ===
    inquiry_type = str(next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryType), "general"))
    if inquiry_type == "causal":
        causal_graph = dataset.graph(_graph_uri("graph/causal"))

        # Collect inquiry member entities (boundary + flow nodes)
        members = boundary_in | boundary_out | all_flow_nodes

        # Filter causal edges to inquiry members
        causal_edges = [
            (str(s), str(o))
            for s, _, o in causal_graph.triples((None, SCIC_NS.causes, None))
            if s in members and o in members
        ]

        # causal_acyclicity
        if _has_cycle(causal_edges):
            results.append(
                {
                    "check": "causal_acyclicity",
                    "status": "fail",
                    "message": "Cycle detected in scic:causes edges among inquiry variables",
                }
            )
        else:
            results.append(
                {
                    "check": "causal_acyclicity",
                    "status": "pass",
                    "message": "Causal edges are acyclic",
                }
            )

        # confounders_declared — check for common causes without scic:confounds
        # A "common cause" is a variable that causes 2+ other inquiry variables
        children: dict[str, set[str]] = {}
        for s_str, o_str in causal_edges:
            children.setdefault(s_str, set()).add(o_str)

        common_causes = [parent for parent, targets in children.items() if len(targets) >= 2]

        # Check if common causes have scic:confounds edges declared
        confound_sources: set[str] = set()
        for s, _p, o in causal_graph.triples((None, SCIC_NS.confounds, None)):
            if s in members:
                confound_sources.add(str(s))

        undeclared = [c for c in common_causes if c not in confound_sources]
        if undeclared:
            short_names = [shorten_uri(u) for u in undeclared]
            results.append(
                {
                    "check": "confounders_declared",
                    "status": "warn",
                    "message": f"Common cause(s) without scic:confounds declaration: {', '.join(short_names)}",
                }
            )
        else:
            results.append(
                {
                    "check": "confounders_declared",
                    "status": "pass",
                    "message": "All common causes have confounders declared"
                    if common_causes
                    else "No common causes found",
                }
            )

        # identifiability + adjustment_sets — requires pgmpy (optional)
        treatment_uri = next(inquiry_graph.objects(inquiry_uri, SCI_NS.treatment), None)
        outcome_uri = next(inquiry_graph.objects(inquiry_uri, SCI_NS.outcome), None)

        if not treatment_uri or not outcome_uri:
            results.append(
                {
                    "check": "identifiability",
                    "status": "skip",
                    "message": "Treatment or outcome not set — cannot check identifiability",
                }
            )
            results.append(
                {
                    "check": "adjustment_sets",
                    "status": "skip",
                    "message": "Treatment or outcome not set — cannot compute adjustment sets",
                }
            )
        else:
            treatment_name = shorten_uri(str(treatment_uri)).rsplit("/", 1)[-1]
            outcome_name = shorten_uri(str(outcome_uri)).rsplit("/", 1)[-1]

            _pgmpy_available = True
            try:
                try:
                    from pgmpy.models import DiscreteBayesianNetwork as _BN
                except ImportError:
                    from pgmpy.models import BayesianNetwork as _BN
                from pgmpy.inference import CausalInference
            except ImportError:
                _pgmpy_available = False

            if not _pgmpy_available:
                results.append(
                    {
                        "check": "identifiability",
                        "status": "skip",
                        "message": "pgmpy not installed — install with: uv add pgmpy",
                    }
                )
                results.append(
                    {
                        "check": "adjustment_sets",
                        "status": "skip",
                        "message": "pgmpy not installed — install with: uv add pgmpy",
                    }
                )
            else:
                edge_list = [
                    (shorten_uri(s).rsplit("/", 1)[-1], shorten_uri(o).rsplit("/", 1)[-1]) for s, o in causal_edges
                ]
                if edge_list:
                    try:
                        model = _BN(edge_list)
                        ci = CausalInference(model)
                        adj_sets = ci.get_all_backdoor_adjustment_sets(treatment_name, outcome_name)
                        adj_list = [set(s) for s in adj_sets]
                        if adj_list:
                            results.append(
                                {
                                    "check": "identifiability",
                                    "status": "pass",
                                    "message": f"Causal effect {treatment_name} -> {outcome_name}"
                                    " is identifiable via back-door",
                                }
                            )
                            sets_str = "; ".join(str(s) for s in adj_list)
                            results.append(
                                {
                                    "check": "adjustment_sets",
                                    "status": "info",
                                    "message": f"Valid adjustment sets: {sets_str}",
                                }
                            )
                        else:
                            results.append(
                                {
                                    "check": "identifiability",
                                    "status": "warn",
                                    "message": f"No valid back-door adjustment set found for"
                                    f" {treatment_name} -> {outcome_name}",
                                }
                            )
                            results.append(
                                {
                                    "check": "adjustment_sets",
                                    "status": "info",
                                    "message": "No valid adjustment sets found",
                                }
                            )
                    except Exception as exc:
                        results.append(
                            {
                                "check": "identifiability",
                                "status": "warn",
                                "message": f"Could not compute identifiability: {exc}",
                            }
                        )
                        results.append(
                            {
                                "check": "adjustment_sets",
                                "status": "skip",
                                "message": f"Could not compute adjustment sets: {exc}",
                            }
                        )
                else:
                    results.append(
                        {
                            "check": "identifiability",
                            "status": "skip",
                            "message": "No causal edges found — cannot assess identifiability",
                        }
                    )
                    results.append(
                        {
                            "check": "adjustment_sets",
                            "status": "skip",
                            "message": "No causal edges found",
                        }
                    )

    # 6. provenance_completeness — specified+ inquiries: all assumptions must have prov:wasDerivedFrom
    if status != "sketch":
        provenance_graph = dataset.graph(_graph_uri("graph/provenance"))
        missing_prov: list[str] = []
        for s, _p, _o in inquiry_graph.triples((None, RDF.type, SCI_NS.Assumption)):
            has_source = any(True for _ in provenance_graph.triples((s, PROV.wasDerivedFrom, None)))
            if not has_source:
                # Also check knowledge graph for inline source
                has_source = any(True for _ in knowledge.triples((s, PROV.wasDerivedFrom, None)))
            if not has_source:
                missing_prov.append(str(s))

        if missing_prov:
            results.append(
                {
                    "check": "provenance_completeness",
                    "status": "fail",
                    "message": f"{len(missing_prov)} assumption(s) missing provenance (prov:wasDerivedFrom)",
                    "details": missing_prov,
                }
            )
        else:
            results.append(
                {
                    "check": "provenance_completeness",
                    "status": "pass",
                    "message": "All assumptions have provenance",
                }
            )

    return results


def import_snapshot(graph_path: Path, snapshot_path: Path) -> int:
    """Import a Turtle snapshot into :graph/knowledge and record provenance. Returns triple count."""
    if not snapshot_path.exists():
        raise click.ClickException(f"Snapshot file not found: {snapshot_path}")

    from rdflib import Graph

    snapshot = Graph()
    snapshot.parse(str(snapshot_path), format="turtle")
    imported_count = len(snapshot)

    if imported_count == 0:
        raise click.ClickException(f"Snapshot contains no triples: {snapshot_path}")

    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))

    for triple in snapshot:
        knowledge.add(triple)

    # Record import provenance
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    import_uri = URIRef(PROJECT_NS[f"import/{_slug(snapshot_path.stem)}"])
    import_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for triple in list(provenance.triples((import_uri, None, None))):
        provenance.remove(triple)

    provenance.add((import_uri, RDF.type, PROV.Activity))
    provenance.add((import_uri, SCHEMA_NS.name, Literal(f"Import: {snapshot_path.name}")))
    provenance.add((import_uri, PROV.generatedAtTime, Literal(import_time, datatype=XSD.dateTime)))
    provenance.add((import_uri, SCHEMA_NS.size, Literal(imported_count, datatype=XSD.integer)))

    _save_dataset(dataset, graph_path)
    return imported_count


def stamp_revision(graph_path: Path) -> str:
    """Update graph revision metadata without adding entities. Returns the revision timestamp."""
    dataset = _load_dataset(graph_path)
    _save_dataset(dataset, graph_path)

    # Read back the stamped time
    dataset = _load_dataset(graph_path)
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    time_obj = next(provenance.objects(REVISION_URI, SCHEMA_NS.dateModified), None)
    return str(time_obj) if time_obj else "unknown"


PREDICATE_REGISTRY: list[dict[str, str]] = [
    {"predicate": "skos:related", "description": "General association between concepts", "layer": "graph/knowledge"},
    {"predicate": "skos:broader", "description": "Broader concept hierarchy", "layer": "graph/knowledge"},
    {"predicate": "skos:narrower", "description": "Narrower concept hierarchy", "layer": "graph/knowledge"},
    {"predicate": "cito:supports", "description": "Relation-claim predicate for support evidence", "layer": "relation-claim"},
    {"predicate": "cito:disputes", "description": "Relation-claim predicate for disputing evidence", "layer": "relation-claim"},
    {"predicate": "cito:discusses", "description": "Relation-claim predicate for claim/hypothesis discussion", "layer": "relation-claim"},
    {"predicate": "cito:extends", "description": "Work extends prior research", "layer": "graph/knowledge"},
    {"predicate": "cito:usesMethodIn", "description": "Uses method from another work", "layer": "graph/knowledge"},
    {"predicate": "cito:citesAsDataSource", "description": "Cites as data source", "layer": "graph/knowledge"},
    {"predicate": "sci:evaluates", "description": "Benchmark evaluates model/method", "layer": "graph/knowledge"},
    {"predicate": "sci:hasModality", "description": "Model/method operates on modality", "layer": "graph/knowledge"},
    {"predicate": "sci:detectedBy", "description": "Feature detected by method/tool", "layer": "graph/knowledge"},
    {"predicate": "sci:storedIn", "description": "Data stored in database/repository", "layer": "graph/knowledge"},
    {"predicate": "sci:measuredBy", "description": "Variable measured by dataset", "layer": "graph/datasets"},
    {"predicate": "sci:projectStatus", "description": "Project status of entity", "layer": "graph/knowledge"},
    {"predicate": "sci:confidence", "description": "Confidence score (0.0-1.0)", "layer": "graph/provenance"},
    {"predicate": "sci:evidenceType", "description": "Evidence classification for claims/evidence items", "layer": "graph/provenance"},
    {"predicate": "sci:epistemicStatus", "description": "Epistemic status of claim", "layer": "graph/provenance"},
    {"predicate": "sci:maturity", "description": "Maturity of open question", "layer": "graph/knowledge"},
    {"predicate": "scic:causes", "description": "Causal relationship", "layer": "graph/causal"},
    {"predicate": "scic:confounds", "description": "Confounding relationship", "layer": "graph/causal"},
    {"predicate": "prov:wasDerivedFrom", "description": "Provenance source", "layer": "graph/provenance"},
    # Inquiry predicates
    {"predicate": "sci:target", "description": "Inquiry targets hypothesis/question", "layer": "inquiry"},
    {"predicate": "sci:boundaryRole", "description": "Boundary classification within inquiry", "layer": "inquiry"},
    {"predicate": "sci:inquiryStatus", "description": "Inquiry lifecycle status", "layer": "inquiry"},
    {"predicate": "sci:feedsInto", "description": "Data/information flow", "layer": "inquiry"},
    {"predicate": "sci:assumes", "description": "Dependency on assumption", "layer": "inquiry"},
    {"predicate": "sci:produces", "description": "Transformation yields output", "layer": "inquiry"},
    {"predicate": "sci:paramValue", "description": "Parameter value", "layer": "inquiry"},
    {"predicate": "sci:paramSource", "description": "Parameter source type", "layer": "inquiry"},
    {"predicate": "sci:paramRef", "description": "Parameter reference", "layer": "inquiry"},
    {"predicate": "sci:paramNote", "description": "Parameter rationale", "layer": "inquiry"},
    {"predicate": "sci:observability", "description": "Variable observability status", "layer": "graph/knowledge"},
    {"predicate": "sci:backedByClaim", "description": "Inquiry edge backed by relation claim", "layer": "inquiry"},
    {"predicate": "sci:validatedBy", "description": "Step validated by criterion", "layer": "inquiry"},
    {"predicate": "sci:inquiryType", "description": "Inquiry type (general, causal)", "layer": "inquiry"},
    {
        "predicate": "sci:treatment",
        "description": "Treatment/intervention variable in causal inquiry",
        "layer": "inquiry",
    },
    {"predicate": "sci:outcome", "description": "Outcome variable in causal inquiry", "layer": "inquiry"},
    # Model-parameter structure predicates (natural-systems-guide)
    {"predicate": "sci:hasParameter", "description": "Model uses canonical parameter", "layer": "graph/knowledge"},
    {"predicate": "sci:approximates", "description": "Model approximates another model", "layer": "graph/knowledge"},
    {"predicate": "sci:limitOf", "description": "Model is a limit case of another", "layer": "graph/knowledge"},
    {"predicate": "sci:dualOf", "description": "Models are dual formulations", "layer": "graph/knowledge"},
    {"predicate": "sci:coarseGrainOf", "description": "Model is coarse-grained version", "layer": "graph/knowledge"},
    {"predicate": "sci:coupledWith", "description": "Models coupled in multi-physics", "layer": "graph/knowledge"},
    {
        "predicate": "sci:analogousTo",
        "description": "Structure-preserving cross-domain analogy",
        "layer": "graph/knowledge",
    },
    {
        "predicate": "sci:competesWithParam",
        "description": "Parameters have competing effects",
        "layer": "graph/knowledge",
    },
    {
        "predicate": "sci:controlsOnset",
        "description": "Parameter controls bifurcation/onset",
        "layer": "graph/knowledge",
    },
]


def query_predicates() -> list[dict[str, str]]:
    return list(PREDICATE_REGISTRY)


def validate_graph(graph_path: Path) -> tuple[list[dict[str, str]], bool]:
    rows: list[dict[str, str]] = []

    try:
        dataset = _load_dataset(graph_path)
    except Exception as exc:  # noqa: BLE001
        rows.append(
            {
                "check": "parseable_trig",
                "status": "fail",
                "details": f"failed to parse graph.trig: {exc}",
            }
        )
        return rows, True

    rows.append(
        {
            "check": "parseable_trig",
            "status": "pass",
            "details": "graph.trig parsed successfully",
        }
    )

    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    causal = dataset.graph(_graph_uri("graph/causal"))

    provenance_failures = 0
    for entity_type in (SCI_NS.Claim, SCI_NS.Hypothesis):
        for entity, _, _ in knowledge.triples((None, RDF.type, entity_type)):
            if not any(provenance.triples((entity, PROV.wasDerivedFrom, None))):
                provenance_failures += 1

    if provenance_failures:
        rows.append(
            {
                "check": "provenance_completeness",
                "status": "fail",
                "details": f"{provenance_failures} claim/hypothesis entities missing prov:wasDerivedFrom",
            }
        )
    else:
        rows.append(
            {
                "check": "provenance_completeness",
                "status": "pass",
                "details": "all claims and hypotheses have provenance links",
            }
        )

    edges = [(str(subj), str(obj)) for subj, _, obj in causal.triples((None, SCIC_NS.causes, None))]
    if _has_cycle(edges):
        rows.append(
            {
                "check": "causal_acyclicity",
                "status": "fail",
                "details": "cycle detected in scic:causes edges",
            }
        )
    else:
        rows.append(
            {
                "check": "causal_acyclicity",
                "status": "pass",
                "details": "causal graph is acyclic",
            }
        )

    # Orphaned nodes: entities with rdf:type but no other triples as subject or object
    typed_entities = set()
    for entity_type in (SCI_NS.Concept, SCI_NS.Claim, SCI_NS.Hypothesis, SCI_NS.Question, SCI_NS.Task):
        for entity, _, _ in knowledge.triples((None, RDF.type, entity_type)):
            typed_entities.add(entity)
    for entity, _, _ in knowledge.triples((None, RDF.type, SCIC_NS.Variable)):
        typed_entities.add(entity)

    # Predicates that describe the node itself (metadata), not edges to other entities
    metadata_preds = {
        RDF.type,
        SKOS.prefLabel,
        SKOS.note,
        SKOS.definition,
        SCHEMA_NS.identifier,
        SCHEMA_NS.text,
        SCI_NS.maturity,
        SCI_NS.projectStatus,
    }

    orphaned = 0
    for entity in typed_entities:
        # Count triples where entity appears as subject (excluding metadata predicates)
        as_subject = sum(1 for _, p, _ in knowledge.triples((entity, None, None)) if p not in metadata_preds)
        # Count triples where entity appears as object
        as_object = sum(1 for _ in knowledge.triples((None, None, entity)))
        if as_subject == 0 and as_object == 0:
            orphaned += 1

    if orphaned:
        rows.append(
            {
                "check": "orphaned_nodes",
                "status": "warn",
                "details": f"{orphaned} entities have no edges to other entities",
            }
        )
    else:
        rows.append(
            {
                "check": "orphaned_nodes",
                "status": "pass",
                "details": "all entities have at least one edge",
            }
        )

    has_failures = any(row["status"] == "fail" for row in rows)
    return rows, has_failures


def diff_graph_inputs(graph_path: Path, mode: str) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    baseline = _read_revision_manifest(dataset)
    current = _build_input_manifest(graph_path=graph_path)

    rows: list[dict[str, str]] = []

    for rel_path, current_meta in current.items():
        baseline_meta = baseline.get(rel_path)
        if baseline_meta is None:
            rows.append({"path": rel_path, "status": "stale", "reason": "new_file"})
            continue

        mtime_changed = current_meta["mtime_ns"] != baseline_meta.get("mtime_ns")
        hash_changed = current_meta["sha256"] != baseline_meta.get("sha256")

        reason: str | None = None
        if mode == "mtime":
            if mtime_changed:
                reason = "mtime_changed"
        elif mode == "hash":
            if hash_changed:
                reason = "hash_changed"
        elif mode == "hybrid":
            if hash_changed:
                reason = "hash_changed"
            elif mtime_changed:
                reason = "mtime_changed"
        else:
            raise click.ClickException(f"Unsupported diff mode: {mode}")

        if reason is not None:
            rows.append({"path": rel_path, "status": "stale", "reason": reason})

    for removed in sorted(set(baseline.keys()) - set(current.keys())):
        rows.append({"path": removed, "status": "stale", "reason": "removed_file"})

    rows.sort(key=lambda row: row["path"])
    return rows


def query_neighborhood(
    graph_path: Path,
    center: str,
    hops: int,
    graph_layer: str,
    limit: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    layer = dataset.graph(_graph_uri(graph_layer))

    center_uri = _resolve_center_entity(center)
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
    return rows[:limit]


def query_claims(graph_path: Path, about: str, limit: int) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    tokens = _about_tokens(about)
    rows: list[dict[str, str]] = []
    for claim_uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Claim)):
        text_obj = next(knowledge.objects(claim_uri, SCHEMA_NS.text), None)
        if text_obj is None:
            continue
        text = str(text_obj)
        if not any(token in text.lower() for token in tokens):
            continue

        sources = sorted({str(src) for src in provenance.objects(claim_uri, PROV.wasDerivedFrom)})
        rows.append(
            {
                "claim": str(claim_uri),
                "text": text,
                "sources": "; ".join(sources),
            }
        )
    return rows[:limit]


def query_evidence(
    graph_path: Path,
    target_ref: str,
    limit: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    target_uri = _resolve_center_entity(target_ref)
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

    return rows[:limit]


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

    for relation_claim_uri, _, predicate_uri in knowledge.triples((None, SCI_NS.claimPredicate, None)):
        if not isinstance(relation_claim_uri, URIRef) or not isinstance(predicate_uri, URIRef):
            continue
        if (relation_claim_uri, RDF.type, SCI_NS.RelationClaim) not in knowledge:
            continue
        if not any(predicate_uri == allowed_predicate for allowed_predicate, _ in allowed_predicates):
            continue

        claim_object = next(knowledge.objects(relation_claim_uri, SCI_NS.claimObject), None)
        if claim_object != target_uri:
            continue

        claim_subject = next(knowledge.objects(relation_claim_uri, SCI_NS.claimSubject), None)
        evidence_uri = claim_subject if isinstance(claim_subject, URIRef) else relation_claim_uri
        relation = next(
            label for allowed_predicate, label in allowed_predicates if predicate_uri == allowed_predicate
        )
        _append_row(
            rows=rows,
            seen=seen,
            knowledge=knowledge,
            provenance=provenance,
            evidence_uri=evidence_uri,
            relation=relation,
            fallback_uri=relation_claim_uri,
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
    text_obj = next(knowledge.objects(evidence_uri, SCHEMA_NS.text), None)
    text = str(text_obj) if text_obj else ""

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


def _linked_claims_for_hypothesis(knowledge, hypothesis_uri: URIRef) -> list[URIRef]:
    linked_claims: list[URIRef] = []
    seen: set[URIRef] = set()

    for subj, _, _ in knowledge.triples((None, CITO_NS.discusses, hypothesis_uri)):
        if isinstance(subj, URIRef) and (subj, RDF.type, SCI_NS.Claim) in knowledge and subj not in seen:
            linked_claims.append(subj)
            seen.add(subj)

    for relation_claim_uri, _, _ in knowledge.triples((None, SCI_NS.claimPredicate, CITO_NS.discusses)):
        if not isinstance(relation_claim_uri, URIRef):
            continue
        if (relation_claim_uri, RDF.type, SCI_NS.RelationClaim) not in knowledge:
            continue

        claim_object = next(knowledge.objects(relation_claim_uri, SCI_NS.claimObject), None)
        claim_subject = next(knowledge.objects(relation_claim_uri, SCI_NS.claimSubject), None)
        if claim_object == hypothesis_uri and isinstance(claim_subject, URIRef) and claim_subject not in seen:
            linked_claims.append(claim_subject)
            seen.add(claim_subject)

    return linked_claims


def _source_strings(provenance, primary_uri: URIRef, fallback_uri: URIRef | None = None) -> list[str]:
    sources = {str(src) for src in provenance.objects(primary_uri, PROV.wasDerivedFrom)}
    if fallback_uri is not None:
        sources.update(str(src) for src in provenance.objects(fallback_uri, PROV.wasDerivedFrom))
    return sorted(sources)


def _evidence_targets_for_uri(knowledge, target_uri: URIRef) -> list[URIRef]:
    if (target_uri, RDF.type, SCI_NS.Hypothesis) not in knowledge:
        return [target_uri]
    return [target_uri, *_linked_claims_for_hypothesis(knowledge, target_uri)]


def _collect_evidence_signals(knowledge, provenance, target_uri: URIRef) -> dict[str, object]:
    support_sources: set[str] = set()
    dispute_sources: set[str] = set()
    support_items: set[str] = set()
    dispute_items: set[str] = set()

    def record(relation: str, evidence_uri: URIRef, fallback_uri: URIRef | None = None) -> None:
        source_strings = tuple(_source_strings(provenance, evidence_uri, fallback_uri))
        item = str(evidence_uri)
        if relation == "supports":
            support_items.add(item)
            support_sources.update(source_strings)
            return
        dispute_items.add(item)
        dispute_sources.update(source_strings)

    for aggregate_target in _evidence_targets_for_uri(knowledge, target_uri):
        for subj, _, _ in knowledge.triples((None, CITO_NS.supports, aggregate_target)):
            if isinstance(subj, URIRef):
                record("supports", subj)
        for subj, _, _ in knowledge.triples((None, CITO_NS.disputes, aggregate_target)):
            if isinstance(subj, URIRef):
                record("disputes", subj)

        for relation_claim_uri, _, predicate_uri in knowledge.triples((None, SCI_NS.claimPredicate, None)):
            if not isinstance(relation_claim_uri, URIRef) or not isinstance(predicate_uri, URIRef):
                continue
            if (relation_claim_uri, RDF.type, SCI_NS.RelationClaim) not in knowledge:
                continue
            if predicate_uri not in (CITO_NS.supports, CITO_NS.disputes):
                continue

            claim_object = next(knowledge.objects(relation_claim_uri, SCI_NS.claimObject), None)
            if claim_object != aggregate_target:
                continue

            claim_subject = next(knowledge.objects(relation_claim_uri, SCI_NS.claimSubject), None)
            evidence_uri = claim_subject if isinstance(claim_subject, URIRef) else relation_claim_uri
            record("supports" if predicate_uri == CITO_NS.supports else "disputes", evidence_uri, relation_claim_uri)

    total_evidence = len(support_items) + len(dispute_items)
    unique_source_count = len(support_sources | dispute_sources)
    if unique_source_count == 0 and total_evidence > 0:
        unique_source_count = total_evidence

    return {
        "support_count": len(support_items),
        "dispute_count": len(dispute_items),
        "support_sources": support_sources,
        "dispute_sources": dispute_sources,
        "source_count": unique_source_count,
    }


def _evidence_type_strings(provenance, primary_uri: URIRef, fallback_uri: URIRef | None = None) -> set[str]:
    evidence_types = {str(value) for value in provenance.objects(primary_uri, SCI_NS.evidenceType)}
    if fallback_uri is not None:
        evidence_types.update(str(value) for value in provenance.objects(fallback_uri, SCI_NS.evidenceType))
    return {value for value in evidence_types if value}


def _collect_evidence_types(knowledge, provenance, target_uri: URIRef) -> set[str]:
    evidence_types: set[str] = set()

    def record(evidence_uri: URIRef, fallback_uri: URIRef | None = None) -> None:
        evidence_types.update(_evidence_type_strings(provenance, evidence_uri, fallback_uri))

    for aggregate_target in _evidence_targets_for_uri(knowledge, target_uri):
        for subj, _, _ in knowledge.triples((None, CITO_NS.supports, aggregate_target)):
            if isinstance(subj, URIRef):
                record(subj)
        for subj, _, _ in knowledge.triples((None, CITO_NS.disputes, aggregate_target)):
            if isinstance(subj, URIRef):
                record(subj)

        for relation_claim_uri, _, predicate_uri in knowledge.triples((None, SCI_NS.claimPredicate, None)):
            if not isinstance(relation_claim_uri, URIRef) or not isinstance(predicate_uri, URIRef):
                continue
            if (relation_claim_uri, RDF.type, SCI_NS.RelationClaim) not in knowledge:
                continue
            if predicate_uri not in (CITO_NS.supports, CITO_NS.disputes):
                continue

            claim_object = next(knowledge.objects(relation_claim_uri, SCI_NS.claimObject), None)
            if claim_object != aggregate_target:
                continue

            claim_subject = next(knowledge.objects(relation_claim_uri, SCI_NS.claimSubject), None)
            evidence_uri = claim_subject if isinstance(claim_subject, URIRef) else relation_claim_uri
            record(evidence_uri, relation_claim_uri)

    return evidence_types


def _belief_state(
    support_count: int,
    dispute_count: int,
    source_count: int,
) -> str:
    if dispute_count > 0:
        return "contested"
    if support_count == 0:
        return "speculative"
    if source_count <= 1:
        return "fragile"
    if support_count >= 2 and source_count >= 2:
        return "well_supported"
    return "supported"


def _summary_targets(knowledge, *, include_hypotheses: bool) -> list[URIRef]:
    entity_types = [SCI_NS.Claim]
    if include_hypotheses:
        entity_types.append(SCI_NS.Hypothesis)

    seen: set[URIRef] = set()
    targets: list[URIRef] = []
    for entity_type in entity_types:
        for uri, _, _ in knowledge.triples((None, RDF.type, entity_type)):
            if not isinstance(uri, URIRef) or uri in seen:
                continue
            seen.add(uri)
            targets.append(uri)
    return targets


def _claim_summary_data(knowledge, provenance, uri: URIRef) -> ClaimSummaryData | None:
    evidence_summary = _collect_evidence_signals(knowledge, provenance, uri)
    support_count = cast(int, evidence_summary["support_count"])
    dispute_count = cast(int, evidence_summary["dispute_count"])
    source_count = cast(int, evidence_summary["source_count"])
    evidence_types = sorted(_collect_evidence_types(knowledge, provenance, uri))
    has_empirical_data = any(
        evidence_type in {"empirical_data_evidence", "benchmark_evidence"} for evidence_type in evidence_types
    )
    belief_state = _belief_state(support_count=support_count, dispute_count=dispute_count, source_count=source_count)

    status_obj = next(provenance.objects(uri, SCI_NS.epistemicStatus), None)
    status = str(status_obj) if status_obj else ""
    conf_obj = next(provenance.objects(uri, SCI_NS.confidence), None)
    confidence: float | None = None
    if conf_obj is not None:
        try:
            confidence = float(str(conf_obj))
        except ValueError:
            pass

    signals: list[str] = []
    risk_score = 0.0
    total_evidence = support_count + dispute_count
    if dispute_count > 0:
        signals.append("contested")
        risk_score += 3.0
    if support_count > 0 and source_count <= 1:
        signals.append("single_source")
        risk_score += 2.0
    if total_evidence > 0 and not has_empirical_data:
        signals.append("no_empirical_data")
        risk_score += 1.5
    if total_evidence == 0:
        signals.append("no_evidence")
        risk_score += 1.0
    if confidence is not None and confidence < 0.5:
        signals.append("low_confidence")
        risk_score += 1.0 + (0.5 - confidence)
    if status:
        signals.append(f"status:{status}")
        risk_score += 0.5

    if total_evidence == 0 and confidence is None and not status:
        return None

    text_obj = next(knowledge.objects(uri, SCHEMA_NS.text), None)
    text = str(text_obj) if text_obj else _short_name(str(uri))
    label_obj = next(knowledge.objects(uri, SKOS.prefLabel), None)
    label = str(label_obj) if label_obj else text

    return {
        "uri": uri,
        "claim": str(uri),
        "label": label,
        "text": text,
        "belief_state": belief_state,
        "support_count": support_count,
        "dispute_count": dispute_count,
        "source_count": source_count,
        "evidence_types": evidence_types,
        "has_empirical_data": has_empirical_data,
        "signals": signals,
        "risk_score": risk_score,
    }


def _format_claim_summary_row(summary: ClaimSummaryData) -> dict[str, str]:
    evidence_types = summary["evidence_types"]
    signals = summary["signals"]
    return {
        "claim": str(summary["claim"]),
        "label": str(summary["label"]),
        "text": str(summary["text"]),
        "belief_state": str(summary["belief_state"]),
        "support_count": str(summary["support_count"]),
        "dispute_count": str(summary["dispute_count"]),
        "source_count": str(summary["source_count"]),
        "evidence_types": "; ".join(evidence_types) if evidence_types else "-",
        "has_empirical_data": "yes" if bool(summary["has_empirical_data"]) else "no",
        "signals": "; ".join(signals) if signals else "-",
        "risk_score": f"{summary['risk_score']:.2f}",
    }


def _claim_summaries(knowledge, provenance, *, include_hypotheses: bool) -> list[ClaimSummaryData]:
    rows: list[ClaimSummaryData] = []
    for uri in _summary_targets(knowledge, include_hypotheses=include_hypotheses):
        summary = _claim_summary_data(knowledge, provenance, uri)
        if summary is not None:
            rows.append(summary)
    return rows


def query_dashboard_summary(
    graph_path: Path,
    top: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    rows = [_format_claim_summary_row(summary) for summary in _claim_summaries(knowledge, provenance, include_hypotheses=True)]
    rows.sort(key=lambda row: (-float(row["risk_score"]), row["text"]))
    return rows[:top]


def _hypotheses_for_claim(knowledge, claim_uri: URIRef) -> set[URIRef]:
    hypotheses: set[URIRef] = set()

    for _, _, obj in knowledge.triples((claim_uri, CITO_NS.discusses, None)):
        if isinstance(obj, URIRef) and (obj, RDF.type, SCI_NS.Hypothesis) in knowledge:
            hypotheses.add(obj)

    for relation_claim_uri, _, _ in knowledge.triples((None, SCI_NS.claimPredicate, CITO_NS.discusses)):
        if not isinstance(relation_claim_uri, URIRef):
            continue
        if (relation_claim_uri, RDF.type, SCI_NS.RelationClaim) not in knowledge:
            continue

        claim_subject = next(knowledge.objects(relation_claim_uri, SCI_NS.claimSubject), None)
        claim_object = next(knowledge.objects(relation_claim_uri, SCI_NS.claimObject), None)
        if claim_subject != claim_uri:
            continue
        if isinstance(claim_object, URIRef) and (claim_object, RDF.type, SCI_NS.Hypothesis) in knowledge:
            hypotheses.add(claim_object)

    return hypotheses


def _claim_summary_adjacency(knowledge, summary_uris: set[URIRef]) -> dict[URIRef, set[URIRef]]:
    adjacency: dict[URIRef, set[URIRef]] = {uri: set() for uri in summary_uris}
    link_predicates = {CITO_NS.supports, CITO_NS.disputes, CITO_NS.discusses}

    def connect(left: URIRef, right: URIRef) -> None:
        if left == right:
            return
        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)

    for subj, predicate, obj in knowledge:
        if predicate not in link_predicates:
            continue
        if isinstance(subj, URIRef) and isinstance(obj, URIRef) and subj in summary_uris and obj in summary_uris:
            connect(subj, obj)

    for relation_claim_uri, _, predicate_uri in knowledge.triples((None, SCI_NS.claimPredicate, None)):
        if not isinstance(relation_claim_uri, URIRef) or predicate_uri not in link_predicates:
            continue
        if (relation_claim_uri, RDF.type, SCI_NS.RelationClaim) not in knowledge:
            continue

        claim_subject = next(knowledge.objects(relation_claim_uri, SCI_NS.claimSubject), None)
        claim_object = next(knowledge.objects(relation_claim_uri, SCI_NS.claimObject), None)
        if isinstance(claim_subject, URIRef) and isinstance(claim_object, URIRef):
            if claim_subject in summary_uris and claim_object in summary_uris:
                connect(claim_subject, claim_object)

    claims_by_hypothesis: dict[URIRef, set[URIRef]] = {}
    for claim_uri in summary_uris:
        for hypothesis_uri in _hypotheses_for_claim(knowledge, claim_uri):
            claims_by_hypothesis.setdefault(hypothesis_uri, set()).add(claim_uri)

    for claim_group in claims_by_hypothesis.values():
        for left, right in combinations(sorted(claim_group, key=str), 2):
            connect(left, right)

    return adjacency


def _neighborhood_summary_data_rows(knowledge, provenance, *, hops: int) -> list[NeighborhoodSummaryData]:
    summary_rows = _claim_summaries(knowledge, provenance, include_hypotheses=False)
    by_uri: dict[URIRef, ClaimSummaryData] = {summary["uri"]: summary for summary in summary_rows}
    adjacency = _claim_summary_adjacency(knowledge, set(by_uri))

    rows: list[NeighborhoodSummaryData] = []
    for center_uri, center_summary in by_uri.items():
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

        neighborhood = [by_uri[uri] for uri in sorted(visited, key=str)]
        neighbor_claim_count = max(len(neighborhood) - 1, 0)
        avg_risk_score = sum(float(item["risk_score"]) for item in neighborhood) / len(neighborhood)
        contested_count = sum("contested" in list(item["signals"]) for item in neighborhood)
        single_source_count = sum("single_source" in list(item["signals"]) for item in neighborhood)
        no_empirical_count = sum(not bool(item["has_empirical_data"]) for item in neighborhood)
        structural_fragility = "isolated" if neighbor_claim_count == 0 else "connected"
        neighborhood_risk = avg_risk_score + (0.75 * contested_count) + (0.5 * single_source_count) + (
            0.5 * no_empirical_count
        )

        rows.append(
            {
                "center_uri": center_uri,
                "label": str(center_summary["label"]),
                "text": str(center_summary["text"]),
                "neighbor_claim_count": neighbor_claim_count,
                "avg_risk_score": avg_risk_score,
                "contested_count": contested_count,
                "single_source_count": single_source_count,
                "no_empirical_count": no_empirical_count,
                "structural_fragility": structural_fragility,
                "neighborhood_risk": neighborhood_risk,
            }
        )

    return rows


def _format_neighborhood_summary_row(summary: NeighborhoodSummaryData) -> dict[str, str]:
    return {
        "center_claim": str(summary["center_uri"]),
        "label": str(summary["label"]),
        "text": str(summary["text"]),
        "neighbor_claim_count": str(summary["neighbor_claim_count"]),
        "avg_risk_score": f"{summary['avg_risk_score']:.2f}",
        "contested_count": str(summary["contested_count"]),
        "single_source_count": str(summary["single_source_count"]),
        "no_empirical_count": str(summary["no_empirical_count"]),
        "structural_fragility": str(summary["structural_fragility"]),
        "neighborhood_risk": f"{summary['neighborhood_risk']:.2f}",
    }


def query_neighborhood_summary(
    graph_path: Path,
    top: int,
    hops: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    rows = [_format_neighborhood_summary_row(summary) for summary in _neighborhood_summary_data_rows(knowledge, provenance, hops=hops)]
    rows.sort(key=lambda row: (-float(row["neighborhood_risk"]), row["text"]))
    return rows[:top]


def _question_claims(knowledge, question_uri: URIRef) -> list[URIRef]:
    claims: set[URIRef] = set()
    for claim_uri, _, _ in knowledge.triples((None, SCI_NS.addresses, question_uri)):
        if not isinstance(claim_uri, URIRef):
            continue
        if (claim_uri, RDF.type, SCI_NS.Claim) in knowledge:
            claims.add(claim_uri)

    for related_uri in knowledge.objects(question_uri, SKOS.related):
        if not isinstance(related_uri, URIRef):
            continue
        if (related_uri, RDF.type, SCI_NS.Hypothesis) not in knowledge:
            continue
        claims.update(_linked_claims_for_hypothesis(knowledge, related_uri))

    return sorted(claims, key=str)


def _inquiry_claims(knowledge, inquiry_graph, inquiry_uri: URIRef) -> tuple[list[URIRef], list[URIRef]]:
    backed_claims: set[URIRef] = set()
    for statement_uri, _, _ in inquiry_graph.triples((None, RDF.type, RDF.Statement)):
        for claim_uri in inquiry_graph.objects(statement_uri, SCI_NS.backedByClaim):
            if isinstance(claim_uri, URIRef) and (claim_uri, RDF.type, SCI_NS.Claim) in knowledge:
                backed_claims.add(claim_uri)

    targeted_claims: set[URIRef] = set()
    target_uri = next(inquiry_graph.objects(inquiry_uri, SCI_NS.target), None)
    if isinstance(target_uri, URIRef):
        if (target_uri, RDF.type, SCI_NS.Claim) in knowledge:
            targeted_claims.add(target_uri)
        elif (target_uri, RDF.type, SCI_NS.Hypothesis) in knowledge:
            targeted_claims.update(_linked_claims_for_hypothesis(knowledge, target_uri))
        elif (target_uri, RDF.type, SCI_NS.Question) in knowledge:
            targeted_claims.update(_question_claims(knowledge, target_uri))

    claim_uris = sorted(backed_claims | targeted_claims, key=str)
    return claim_uris, sorted(backed_claims, key=str)


def _rollup_claim_group(
    claim_uris: list[URIRef],
    claim_by_uri: dict[URIRef, ClaimSummaryData],
    neighborhood_by_center: dict[URIRef, NeighborhoodSummaryData],
    *,
    grounding_penalty: float = 0.0,
) -> dict[str, float | int]:
    claim_count = len(claim_uris)
    neighborhood_rows = [neighborhood_by_center[uri] for uri in claim_uris if uri in neighborhood_by_center]
    neighborhood_count = len(neighborhood_rows)

    risk_values: list[float] = []
    contested_claim_count = 0
    single_source_claim_count = 0
    no_empirical_claim_count = 0

    for claim_uri in claim_uris:
        summary = claim_by_uri.get(claim_uri)
        if summary is None:
            risk_values.append(1.0)
            no_empirical_claim_count += 1
            continue

        risk_values.append(float(summary["risk_score"]))
        if "contested" in list(summary["signals"]):
            contested_claim_count += 1
        if "single_source" in list(summary["signals"]):
            single_source_claim_count += 1
        if not bool(summary["has_empirical_data"]):
            no_empirical_claim_count += 1

    avg_risk_score = sum(risk_values) / claim_count if claim_count else 0.0
    avg_neighborhood_risk = (
        sum(float(summary["neighborhood_risk"]) for summary in neighborhood_rows) / neighborhood_count if neighborhood_count else 0.0
    )
    priority_score = (
        avg_risk_score
        + (0.5 * avg_neighborhood_risk)
        + (0.75 * contested_claim_count)
        + (0.5 * single_source_claim_count)
        + (0.5 * no_empirical_claim_count)
        + grounding_penalty
    )

    return {
        "claim_count": claim_count,
        "neighborhood_count": neighborhood_count,
        "avg_risk_score": avg_risk_score,
        "contested_claim_count": contested_claim_count,
        "single_source_claim_count": single_source_claim_count,
        "no_empirical_claim_count": no_empirical_claim_count,
        "priority_score": priority_score,
    }


def _question_summary_data(
    knowledge,
    question_uri: URIRef,
    claim_by_uri: dict[URIRef, ClaimSummaryData],
    neighborhood_by_center: dict[URIRef, NeighborhoodSummaryData],
) -> QuestionSummaryData:
    question_text_obj = next(knowledge.objects(question_uri, SCHEMA_NS.text), None)
    question_text = str(question_text_obj) if question_text_obj else _short_name(str(question_uri))
    question_label_obj = next(knowledge.objects(question_uri, SKOS.prefLabel), None)
    question_identifier_obj = next(knowledge.objects(question_uri, SCHEMA_NS.identifier), None)
    question_label = (
        str(question_label_obj) if question_label_obj else str(question_identifier_obj) if question_identifier_obj else question_text
    )

    metrics = _rollup_claim_group(
        _question_claims(knowledge, question_uri),
        claim_by_uri,
        neighborhood_by_center,
    )
    return {
        "uri": question_uri,
        "question": str(question_uri),
        "label": question_label,
        "text": question_text,
        "claim_count": cast(int, metrics["claim_count"]),
        "neighborhood_count": cast(int, metrics["neighborhood_count"]),
        "avg_risk_score": cast(float, metrics["avg_risk_score"]),
        "contested_claim_count": cast(int, metrics["contested_claim_count"]),
        "single_source_claim_count": cast(int, metrics["single_source_claim_count"]),
        "no_empirical_claim_count": cast(int, metrics["no_empirical_claim_count"]),
        "priority_score": cast(float, metrics["priority_score"]),
    }


def _format_question_summary_row(summary: QuestionSummaryData) -> dict[str, str]:
    return {
        "question": str(summary["question"]),
        "label": str(summary["label"]),
        "text": str(summary["text"]),
        "claim_count": str(summary["claim_count"]),
        "neighborhood_count": str(summary["neighborhood_count"]),
        "avg_risk_score": f"{summary['avg_risk_score']:.2f}",
        "contested_claim_count": str(summary["contested_claim_count"]),
        "single_source_claim_count": str(summary["single_source_claim_count"]),
        "no_empirical_claim_count": str(summary["no_empirical_claim_count"]),
        "priority_score": f"{summary['priority_score']:.2f}",
    }


def query_question_summary(
    graph_path: Path,
    top: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    claim_by_uri = {summary["uri"]: summary for summary in _claim_summaries(knowledge, provenance, include_hypotheses=False)}
    neighborhood_by_center = {
        summary["center_uri"]: summary for summary in _neighborhood_summary_data_rows(knowledge, provenance, hops=1)
    }

    rows = [
        _format_question_summary_row(_question_summary_data(knowledge, question_uri, claim_by_uri, neighborhood_by_center))
        for question_uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Question))
        if isinstance(question_uri, URIRef)
    ]
    rows.sort(key=lambda row: (-float(row["priority_score"]), row["text"]))
    return rows[:top]


def _inquiry_summary_data(
    knowledge,
    inquiry_graph,
    inquiry_uri: URIRef,
    claim_by_uri: dict[URIRef, ClaimSummaryData],
    neighborhood_by_center: dict[URIRef, NeighborhoodSummaryData],
) -> InquirySummaryData:
    claim_uris, backed_claims = _inquiry_claims(knowledge, inquiry_graph, inquiry_uri)
    metrics = _rollup_claim_group(
        claim_uris,
        claim_by_uri,
        neighborhood_by_center,
        grounding_penalty=0.5 if not backed_claims else 0.0,
    )

    label_obj = next(inquiry_graph.objects(inquiry_uri, SKOS.prefLabel), None)
    label = str(label_obj) if label_obj else _short_name(str(inquiry_uri))
    status_obj = next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryStatus), None)
    inquiry_type_obj = next(inquiry_graph.objects(inquiry_uri, SCI_NS.inquiryType), None)

    return {
        "uri": inquiry_uri,
        "inquiry": str(inquiry_uri),
        "label": label,
        "inquiry_type": str(inquiry_type_obj) if inquiry_type_obj else "general",
        "status": str(status_obj) if status_obj else "",
        "claim_count": cast(int, metrics["claim_count"]),
        "backed_claim_count": len(backed_claims),
        "avg_risk_score": cast(float, metrics["avg_risk_score"]),
        "contested_claim_count": cast(int, metrics["contested_claim_count"]),
        "single_source_claim_count": cast(int, metrics["single_source_claim_count"]),
        "no_empirical_claim_count": cast(int, metrics["no_empirical_claim_count"]),
        "priority_score": cast(float, metrics["priority_score"]),
    }


def _format_inquiry_summary_row(summary: InquirySummaryData) -> dict[str, str]:
    return {
        "inquiry": str(summary["inquiry"]),
        "label": str(summary["label"]),
        "inquiry_type": str(summary["inquiry_type"]),
        "status": str(summary["status"]) or "-",
        "claim_count": str(summary["claim_count"]),
        "backed_claim_count": str(summary["backed_claim_count"]),
        "avg_risk_score": f"{summary['avg_risk_score']:.2f}",
        "contested_claim_count": str(summary["contested_claim_count"]),
        "single_source_claim_count": str(summary["single_source_claim_count"]),
        "no_empirical_claim_count": str(summary["no_empirical_claim_count"]),
        "priority_score": f"{summary['priority_score']:.2f}",
    }


def query_inquiry_summary(
    graph_path: Path,
    top: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    claim_by_uri = {summary["uri"]: summary for summary in _claim_summaries(knowledge, provenance, include_hypotheses=False)}
    neighborhood_by_center = {
        summary["center_uri"]: summary for summary in _neighborhood_summary_data_rows(knowledge, provenance, hops=1)
    }

    inquiry_prefix = str(PROJECT_NS) + "inquiry/"
    rows: list[dict[str, str]] = []
    for inquiry_graph in dataset.graphs():
        graph_id = str(inquiry_graph.identifier)
        if not graph_id.startswith(inquiry_prefix):
            continue
        inquiry_uri = URIRef(graph_id)
        if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
            continue

        rows.append(
            _format_inquiry_summary_row(
                _inquiry_summary_data(knowledge, inquiry_graph, inquiry_uri, claim_by_uri, neighborhood_by_center)
            )
        )

    rows.sort(key=lambda row: (-float(row["priority_score"]), row["label"]))
    return rows[:top]


def query_coverage(
    graph_path: Path,
    limit: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    causal = dataset.graph(_graph_uri("graph/causal"))
    datasets_graph = dataset.graph(_graph_uri("graph/datasets"))

    entity_uris: set[URIRef] = set()
    for uri, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Concept)):
        if isinstance(uri, URIRef):
            entity_uris.add(uri)
    for uri, _, _ in causal.triples((None, RDF.type, SCIC_NS.Variable)):
        if isinstance(uri, URIRef):
            entity_uris.add(uri)

    rows: list[dict[str, str]] = []
    for uri in sorted(entity_uris, key=str):
        label_obj = next(knowledge.objects(uri, SKOS.prefLabel), None)
        label = str(label_obj) if label_obj else _short_name(str(uri))

        measured = any(datasets_graph.triples((uri, SCI_NS.measuredBy, None)))

        observed_lit = next(causal.objects(uri, SCIC_NS.isObserved), None)
        if observed_lit is not None:
            observed = str(observed_lit).lower() in ("true", "1")
            observed_str = "yes" if observed else "no"
        else:
            observed_str = "-"

        rows.append(
            {
                "entity": str(uri),
                "label": label,
                "measured": "yes" if measured else "no",
                "observed": observed_str,
            }
        )
    return rows[:limit]


def query_gaps(
    graph_path: Path,
    center: str,
    hops: int,
    limit: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    center_uri = _resolve_center_entity(center)

    # BFS to find neighborhood entities
    adjacency: dict[URIRef, set[URIRef]] = {}
    for subj, _, obj in knowledge:
        if not isinstance(subj, URIRef) or not isinstance(obj, URIRef):
            continue
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
    for uri in sorted(visited, key=str):
        issues: list[str] = []

        # Low connectivity
        degree = len(adjacency.get(uri, set()))
        if degree <= 1:
            issues.append(f"structural_fragility(low_connectivity,degree={degree})")

        # Claim and hypothesis evidence/provenance fragility
        if (uri, RDF.type, SCI_NS.Claim) in knowledge or (uri, RDF.type, SCI_NS.Hypothesis) in knowledge:
            if not any(provenance.triples((uri, PROV.wasDerivedFrom, None))):
                issues.append("missing_provenance")

            evidence_summary = _collect_evidence_signals(knowledge, provenance, uri)
            support_count = int(evidence_summary["support_count"])
            dispute_count = int(evidence_summary["dispute_count"])
            total_evidence = support_count + dispute_count
            source_count = int(evidence_summary["source_count"])
            if support_count > 0 and dispute_count > 0:
                issues.append("evidential_fragility(contested)")
            if total_evidence > 0 and source_count <= 1:
                issues.append("evidential_fragility(single_source)")

        # Low confidence
        conf_obj = next(provenance.objects(uri, SCI_NS.confidence), None)
        if conf_obj is not None:
            try:
                conf = float(str(conf_obj))
                if conf < 0.5:
                    issues.append(f"authored_low_confidence({conf:.2f})")
            except ValueError:
                pass

        if issues:
            label_obj = next(knowledge.objects(uri, SKOS.prefLabel), None)
            if label_obj is None:
                label_obj = next(knowledge.objects(uri, SCHEMA_NS.text), None)
            label = str(label_obj) if label_obj else _short_name(str(uri))

            rows.append(
                {
                    "entity": str(uri),
                    "label": label,
                    "issues": "; ".join(issues),
                }
            )
    return rows[:limit]


def query_uncertainty(
    graph_path: Path,
    top: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    uncertain_statuses = {"disputed", "hypothesized"}

    rows: list[dict[str, str]] = []
    # Collect all entities with epistemic metadata
    seen: set[URIRef] = set()
    for entity_type in (SCI_NS.Claim, SCI_NS.Hypothesis):
        for uri, _, _ in knowledge.triples((None, RDF.type, entity_type)):
            if not isinstance(uri, URIRef) or uri in seen:
                continue
            seen.add(uri)

            status_obj = next(provenance.objects(uri, SCI_NS.epistemicStatus), None)
            status = str(status_obj) if status_obj else ""

            conf_obj = next(provenance.objects(uri, SCI_NS.confidence), None)
            confidence: float | None = None
            if conf_obj is not None:
                try:
                    confidence = float(str(conf_obj))
                except ValueError:
                    pass

            evidence_summary = _collect_evidence_signals(knowledge, provenance, uri)
            support_count = int(evidence_summary["support_count"])
            dispute_count = int(evidence_summary["dispute_count"])
            source_count = int(evidence_summary["source_count"])
            signals: list[str] = []
            risk_score = 0.0

            if support_count > 0 and dispute_count > 0:
                signals.append("contested")
                risk_score += 3.0

            total_evidence = support_count + dispute_count
            if total_evidence > 0 and source_count <= 1:
                signals.append("single_source")
                risk_score += 2.0

            is_uncertain_status = status.lower() in uncertain_statuses
            if is_uncertain_status:
                signals.append(f"status:{status.lower()}")
                risk_score += 1.5

            is_low_confidence = confidence is not None and confidence < 0.5
            if is_low_confidence and confidence is not None:
                signals.append("low_confidence")
                risk_score += 1.0 + (0.5 - confidence)

            if not signals:
                continue

            text_obj = next(knowledge.objects(uri, SCHEMA_NS.text), None)
            text = str(text_obj) if text_obj else _short_name(str(uri))

            rows.append(
                {
                    "entity": str(uri),
                    "text": text,
                    "status": status or "-",
                    "confidence": f"{confidence:.2f}" if confidence is not None else "-",
                    "signals": "; ".join(signals),
                    "support_count": str(support_count),
                    "dispute_count": str(dispute_count),
                    "_sort": str(risk_score),
                }
            )

    rows.sort(key=lambda r: float(r["_sort"]), reverse=True)
    for row in rows:
        del row["_sort"]
    return rows[:top]


def build_graph_dot(
    graph_path: Path,
    graph_layer: str,
    center: str | None,
    hops: int,
    limit: int,
) -> str:
    if center:
        rows = query_neighborhood(
            graph_path=graph_path,
            center=center,
            hops=hops,
            graph_layer=graph_layer,
            limit=limit,
        )
    else:
        dataset = _load_dataset(graph_path)
        layer = dataset.graph(_graph_uri(graph_layer))
        rows = []
        for subj, pred, obj in layer:
            if isinstance(subj, URIRef) and isinstance(obj, URIRef):
                rows.append(
                    {
                        "subject": str(subj),
                        "predicate": str(pred),
                        "object": str(obj),
                    }
                )
            if len(rows) >= limit:
                break

    lines = ["digraph G {", "  rankdir=LR;"]
    nodes: set[str] = set()
    for row in rows:
        subj = row["subject"]
        obj = row["object"]
        pred = row["predicate"]
        nodes.add(subj)
        nodes.add(obj)
        lines.append(f'  "{_short_name(subj)}" -> "{_short_name(obj)}" [label="{_short_name(pred)}"];')
    for node in sorted(nodes):
        lines.append(f'  "{_short_name(node)}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


def _has_cycle(edges: list[tuple[str, str]]) -> bool:
    adjacency: dict[str, list[str]] = {}
    for source, target in edges:
        adjacency.setdefault(source, []).append(target)
        adjacency.setdefault(target, [])

    state: dict[str, int] = {}
    # 0 = unvisited, 1 = visiting, 2 = visited

    def visit(node: str) -> bool:
        status = state.get(node, 0)
        if status == 1:
            return True
        if status == 2:
            return False

        state[node] = 1
        for nxt in adjacency.get(node, []):
            if visit(nxt):
                return True
        state[node] = 2
        return False

    for node in adjacency:
        if state.get(node, 0) == 0 and visit(node):
            return True
    return False


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


def _attach_edge_claims(
    context_graph,
    knowledge,
    context_token: str,
    subject_uri: URIRef,
    predicate_uri: URIRef,
    object_uri: URIRef,
    claim_refs: list[str],
) -> None:
    statement_uri = _edge_statement_uri(context_token, subject_uri, predicate_uri, object_uri)
    context_graph.add((statement_uri, RDF.type, RDF.Statement))
    context_graph.add((statement_uri, RDF.subject, subject_uri))
    context_graph.add((statement_uri, RDF.predicate, predicate_uri))
    context_graph.add((statement_uri, RDF.object, object_uri))

    seen: set[URIRef] = set()
    for claim_ref in claim_refs:
        claim_uri = _resolve_term(claim_ref)
        if claim_uri in seen:
            continue
        seen.add(claim_uri)
        if (claim_uri, RDF.type, SCI_NS.RelationClaim) not in knowledge:
            raise click.ClickException(f"Attached claim '{claim_ref}' must resolve to a relation_claim entity")

        claim_subject = next(knowledge.objects(claim_uri, SCI_NS.claimSubject), None)
        claim_predicate = next(knowledge.objects(claim_uri, SCI_NS.claimPredicate), None)
        claim_object = next(knowledge.objects(claim_uri, SCI_NS.claimObject), None)
        if (claim_subject, claim_predicate, claim_object) != (subject_uri, predicate_uri, object_uri):
            raise click.ClickException(
                f"Attached claim '{claim_ref}' must assert the same subject, predicate, and object as the edge"
            )

        context_graph.add((statement_uri, SCI_NS.backedByClaim, claim_uri))


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
        if prefix in PROJECT_ENTITY_PREFIXES:
            return URIRef(PROJECT_NS[f"{prefix}/{suffix}"])
        supported_prefixes = sorted([*CURIE_PREFIXES.keys(), *PROJECT_ENTITY_PREFIXES])
        raise click.ClickException(
            f"Unknown CURIE prefix '{prefix}'. Supported prefixes: {', '.join(supported_prefixes)}"
        )

    # Bare terms with "/" are already structured paths (e.g. concept/brca1) — preserve as-is
    if "/" in value:
        return URIRef(PROJECT_NS[value])
    # Bare terms without structure get slugified (e.g. "Nucleotide Transformer v2" → nucleotide_transformer_v2)
    return URIRef(PROJECT_NS[_slug(value)])


def _load_dataset(graph_path: Path) -> Dataset:
    if not graph_path.exists():
        raise click.ClickException(f"Graph file not found: {graph_path}")

    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    return dataset


def _save_dataset(dataset: Dataset, graph_path: Path) -> None:
    _upsert_revision_metadata(dataset, graph_path)
    graph_path.write_text(_serialize_dataset_deterministically(dataset), encoding="utf-8")


def save_graph_dataset(dataset: Dataset, graph_path: Path) -> None:
    """Persist a graph dataset with revision metadata refreshed."""
    _save_dataset(dataset, graph_path)


def _upsert_revision_metadata(dataset: Dataset, graph_path: Path) -> None:
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    for triple in list(provenance.triples((REVISION_URI, None, None))):
        provenance.remove(triple)

    manifest = _build_input_manifest(graph_path=graph_path)
    manifest_json = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    revision_time = _revision_timestamp_from_manifest(manifest)

    provenance.add((REVISION_URI, RDF.type, PROV.Entity))
    provenance.add((REVISION_URI, SCHEMA_NS.name, Literal("graph-revision")))
    provenance.add((REVISION_URI, SCHEMA_NS.dateModified, Literal(revision_time, datatype=XSD.dateTime)))
    provenance.add((REVISION_URI, SCHEMA_NS.text, Literal(manifest_json)))

    preview_text = _serialize_dataset_deterministically(dataset)
    graph_hash = hashlib.sha256(preview_text.encode("utf-8")).hexdigest()
    provenance.add((REVISION_URI, SCHEMA_NS.sha256, Literal(graph_hash)))


_SERIALIZER_PREFIXES: tuple[tuple[str, str], ...] = (
    ("rdf", str(RDF)),
    ("prov", str(PROV)),
    ("schema", str(SCHEMA_NS)),
    ("skos", str(SKOS)),
    ("xsd", str(XSD)),
    ("sci", str(SCI_NS)),
    ("scic", str(SCIC_NS)),
    ("biolink", str(BIOLINK_NS)),
    ("cito", str(CITO_NS)),
    ("dcterms", str(DCTERMS_NS)),
)
_SAFE_PREFIX_LOCAL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9._-]*$")


def _serialize_dataset_deterministically(dataset: Dataset) -> str:
    lines = [f"@prefix {prefix}: <{namespace}> ." for prefix, namespace in _SERIALIZER_PREFIXES]
    lines.append("")

    default_graph = dataset.default_graph
    if len(default_graph):
        lines.extend(_render_graph_triples(default_graph))
        lines.append("")

    named_graphs: dict[str, object] = {}
    for graph in dataset.graphs():
        if graph.identifier == default_graph.identifier:
            continue
        named_graphs[str(graph.identifier)] = graph

    ordered_graph_ids = [str(PROJECT_NS[layer]) for layer in GRAPH_LAYERS if str(PROJECT_NS[layer]) in named_graphs]
    ordered_graph_ids.extend(sorted(graph_id for graph_id in named_graphs if graph_id not in ordered_graph_ids))

    for index, graph_id in enumerate(ordered_graph_ids):
        graph = named_graphs[graph_id]
        lines.append(f"<{graph_id}> {{")
        graph_lines = _render_graph_triples(graph, indent="    ")
        lines.extend(graph_lines)
        lines.append("}")
        if index != len(ordered_graph_ids) - 1:
            lines.append("")

    return "\n".join(lines) + "\n"


def _render_graph_triples(graph, *, indent: str = "") -> list[str]:
    triples = sorted(graph, key=_triple_sort_key)
    if not triples:
        return []

    grouped: list[tuple[object, list[tuple[object, list[object]]]]] = []
    for subject, predicate, obj in triples:
        if not grouped or grouped[-1][0] != subject:
            grouped.append((subject, []))
        predicates = grouped[-1][1]
        if not predicates or predicates[-1][0] != predicate:
            predicates.append((predicate, []))
        predicates[-1][1].append(obj)

    lines: list[str] = []
    for subject, predicates in grouped:
        rendered_subject = _format_trig_term(subject)
        for predicate_index, (predicate, objects) in enumerate(predicates):
            rendered_predicate = "a" if predicate == RDF.type else _format_trig_term(predicate)
            rendered_objects = _render_object_list(objects, indent=indent)
            suffix = " ." if predicate_index == len(predicates) - 1 else " ;"
            if predicate_index == 0:
                lines.append(f"{indent}{rendered_subject} {rendered_predicate} {rendered_objects}{suffix}")
                continue
            lines.append(f"{indent}    {rendered_predicate} {rendered_objects}{suffix}")
    return lines


def _render_object_list(objects: list[object], *, indent: str) -> str:
    rendered = [_format_trig_term(obj) for obj in objects]
    if len(rendered) == 1:
        return rendered[0]
    separator = ",\n" + indent + "        "
    return separator.join(rendered)


def _triple_sort_key(triple: tuple[object, object, object]) -> tuple[tuple[int, str], tuple[int, str], tuple[int, str]]:
    subject, predicate, obj = triple
    return (_term_sort_key(subject), _term_sort_key(predicate), _term_sort_key(obj))


def _term_sort_key(term: object) -> tuple[int, str]:
    if isinstance(term, URIRef):
        return (0, str(term))
    if isinstance(term, Literal):
        return (1, f"{term.language or ''}|{term.datatype or ''}|{term}")
    msg = f"Unsupported RDF term for deterministic serialization: {term!r}"
    raise TypeError(msg)


def _format_trig_term(term: object) -> str:
    if isinstance(term, URIRef):
        return _format_uri(term)
    if isinstance(term, Literal):
        return term.n3()
    msg = f"Unsupported RDF term for deterministic serialization: {term!r}"
    raise TypeError(msg)


def _format_uri(uri: URIRef) -> str:
    uri_text = str(uri)
    for prefix, namespace in _SERIALIZER_PREFIXES:
        if not uri_text.startswith(namespace):
            continue
        local = uri_text.removeprefix(namespace)
        if _SAFE_PREFIX_LOCAL_RE.match(local):
            return f"{prefix}:{local}"
    return f"<{uri_text}>"


def _revision_timestamp_from_manifest(manifest: dict[str, dict[str, int | str]]) -> str:
    latest_mtime_ns = max(
        (
            int(metadata["mtime_ns"])
            for metadata in manifest.values()
            if isinstance(metadata, dict) and isinstance(metadata.get("mtime_ns"), int)
        ),
        default=0,
    )
    revision_time = datetime.fromtimestamp(latest_mtime_ns / 1_000_000_000, tz=timezone.utc)
    return revision_time.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_revision_manifest(dataset: Dataset) -> dict[str, dict[str, int | str]]:
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    manifest_literal = next(provenance.objects(REVISION_URI, SCHEMA_NS.text), None)
    if manifest_literal is None:
        return {}

    try:
        loaded = json.loads(str(manifest_literal))
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded, dict):
        return {}

    manifest: dict[str, dict[str, int | str]] = {}
    for key, value in loaded.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        sha = value.get("sha256")
        mtime = value.get("mtime_ns")
        if not isinstance(sha, str):
            continue
        if not isinstance(mtime, int):
            continue
        manifest[key] = {"sha256": sha, "mtime_ns": mtime}
    return manifest


def _build_input_manifest(graph_path: Path) -> dict[str, dict[str, int | str]]:
    project_root = _project_root_from_graph_path(graph_path)

    try:
        from science_tool.paths import resolve_paths

        pp = resolve_paths(project_root)
        include_dirs: list[Path] = [
            pp.doc_dir,
            pp.specs_dir,
            pp.papers_dir / "summaries",
            pp.data_dir,
            pp.code_dir,
            pp.tasks_dir,
            pp.knowledge_dir / "sources",
        ]
        notes_dir = project_root / "notes"
        if notes_dir.is_dir():
            include_dirs.append(notes_dir)
    except Exception:
        include_dirs = [project_root / d for d in ("doc", "specs", "notes", "papers/summaries", "data", "code")]

    include_files = ("RESEARCH_PLAN.md", "science.yaml", "CLAUDE.md", "AGENTS.md")

    files: set[Path] = set()
    for file_name in include_files:
        candidate = project_root / file_name
        if candidate.is_file():
            files.add(candidate)

    for base in include_dirs:
        if not base.is_dir():
            continue
        for candidate in base.rglob("*"):
            if candidate.is_file():
                files.add(candidate)

    manifest: dict[str, dict[str, int | str]] = {}
    for file_path in sorted(files):
        rel_path = file_path.relative_to(project_root).as_posix()
        stat = file_path.stat()
        manifest[rel_path] = {
            "mtime_ns": int(stat.st_mtime_ns),
            "sha256": _sha256_file(file_path),
        }
    return manifest


def _project_root_from_graph_path(graph_path: Path) -> Path:
    if graph_path.name == "graph.trig" and graph_path.parent.name == "knowledge":
        return graph_path.parent.parent
    return graph_path.parent


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _uv_lock(directory: Path) -> None:
    """Run ``uv lock`` in *directory*, silently skipping on failure."""
    try:
        subprocess.run(["uv", "lock"], cwd=directory, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


_NOTEBOOKS_PYPROJECT = """\
[project]
name = "notebooks"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "marimo",
    "altair>=5",
    "click",
    "polars",
    "rdflib>=7",
]
"""


def _copy_viz_notebook(notebooks_dir: Path) -> None:
    """Copy the bundled viz.py marimo notebook into the notebooks directory."""
    dest = notebooks_dir / "viz.py"
    if dest.exists():
        return
    notebooks_dir.mkdir(parents=True, exist_ok=True)
    template = importlib.resources.files("science_tool.graph").joinpath("viz_template.py")
    with importlib.resources.as_file(template) as src:
        import_root = Path(__file__).resolve().parents[2]
        content = src.read_text(encoding="utf-8").replace("__SCIENCE_TOOL_IMPORT_ROOT__", import_root.as_posix())
        dest.write_text(content, encoding="utf-8")

    pyproject = notebooks_dir / "pyproject.toml"
    if not pyproject.exists():
        pyproject.write_text(_NOTEBOOKS_PYPROJECT, encoding="utf-8")
        _uv_lock(notebooks_dir)


def _short_name(uri: str) -> str:
    if uri.startswith(str(PROJECT_NS)):
        return uri.replace(str(PROJECT_NS), "")
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rsplit("/", 1)[-1]
