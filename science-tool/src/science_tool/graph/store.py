from __future__ import annotations

import hashlib
import importlib.resources
import json
import re
import shutil
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

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

VALID_INQUIRY_TYPES: tuple[str, ...] = ("general", "causal")

GRAPH_LAYERS: tuple[str, ...] = (
    "graph/knowledge",
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
    "hypothesis",
    "dataset",
    "question",
    "evidence",
    "inquiry",
}

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
    graph_path: Path, subject: str, predicate: str, obj: str, graph_layer: str
) -> tuple[URIRef, URIRef, URIRef]:
    if graph_layer not in GRAPH_LAYERS:
        raise click.ClickException(f"Unsupported graph layer: {graph_layer}")

    dataset = _load_dataset(graph_path)

    s_uri = _resolve_term(subject)
    p_uri = _resolve_term(predicate)
    o_uri = _resolve_term(obj)

    # Warn if subject/object URIs don't exist in any graph yet
    for uri, label in [(s_uri, subject), (o_uri, obj)]:
        if not any((uri, None, None) in g for g in dataset.graphs()):
            click.echo(f"Warning: '{label}' resolves to {uri} which is not yet in the graph", err=True)

    layer = dataset.graph(_graph_uri(graph_layer))
    layer.add((s_uri, p_uri, o_uri))

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
) -> tuple[URIRef, URIRef, URIRef]:
    """Add a triple to an inquiry's named graph."""
    safe_slug = _slug(inquiry_slug)
    inquiry_uri = URIRef(PROJECT_NS[f"inquiry/{safe_slug}"])

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    if (inquiry_uri, RDF.type, SCI_NS.Inquiry) not in inquiry_graph:
        raise ValueError(f"Inquiry 'inquiry/{safe_slug}' does not exist")

    s_uri = _resolve_term(subject)
    p_uri = _resolve_term(predicate)
    o_uri = _resolve_term(obj)
    inquiry_graph.add((s_uri, p_uri, o_uri))

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

        results.append(
            {
                "slug": slug,
                "label": label,
                "status": status,
                "target": target,
                "created": created,
            }
        )

    return results


def get_inquiry(graph_path: Path, slug: str) -> dict:
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
        DCTERMS_NS.created,
    }
    edges: list[dict[str, str]] = []
    for s, p, o in inquiry_graph:
        if p not in metadata_predicates:
            edges.append({"subject": str(s), "predicate": str(p), "object": str(o)})

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
    target_label = _label_for(target_str)
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
        f"# Inquiry: {info['label']}",
        "",
        f"- **Slug:** {info['slug']}",
        f"- **Target:** {target_label} ({target_id})",
        f"- **Status:** {info['status']}",
        f"- **Created:** {info['created']}",
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
    {"predicate": "cito:supports", "description": "Evidence supports a claim/hypothesis", "layer": "graph/knowledge"},
    {"predicate": "cito:disputes", "description": "Evidence disputes a claim/hypothesis", "layer": "graph/knowledge"},
    {"predicate": "cito:discusses", "description": "Paper discusses a topic", "layer": "graph/knowledge"},
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
    {"predicate": "sci:validatedBy", "description": "Step validated by criterion", "layer": "inquiry"},
    {"predicate": "sci:inquiryType", "description": "Inquiry type (general, causal)", "layer": "inquiry"},
    {
        "predicate": "sci:treatment",
        "description": "Treatment/intervention variable in causal inquiry",
        "layer": "inquiry",
    },
    {"predicate": "sci:outcome", "description": "Outcome variable in causal inquiry", "layer": "inquiry"},
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
    for entity_type in (SCI_NS.Concept, SCI_NS.Claim, SCI_NS.Hypothesis, SCI_NS.Question):
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
    hypothesis_id: str,
    limit: int,
) -> list[dict[str, str]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    hyp_uri = _resolve_center_entity(hypothesis_id)

    rows: list[dict[str, str]] = []

    # Collect all entities that have a cito relation to the hypothesis
    relation_map: dict[URIRef, str] = {}
    for subj, _, _ in knowledge.triples((None, CITO_NS.supports, hyp_uri)):
        if isinstance(subj, URIRef):
            relation_map[subj] = "supports"
    for subj, _, _ in knowledge.triples((None, CITO_NS.disputes, hyp_uri)):
        if isinstance(subj, URIRef):
            relation_map[subj] = "disputes"
    for subj, _, _ in knowledge.triples((None, CITO_NS.discusses, hyp_uri)):
        if isinstance(subj, URIRef):
            relation_map.setdefault(subj, "discusses")

    for ev_uri, relation in relation_map.items():
        text_obj = next(knowledge.objects(ev_uri, SCHEMA_NS.text), None)
        text = str(text_obj) if text_obj else ""

        sources = sorted({str(src) for src in provenance.objects(ev_uri, PROV.wasDerivedFrom)})
        rows.append(
            {
                "evidence": str(ev_uri),
                "relation": relation,
                "text": text,
                "sources": "; ".join(sources),
            }
        )
    return rows[:limit]


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
            issues.append(f"low_connectivity(degree={degree})")

        # Claims missing provenance
        if (uri, RDF.type, SCI_NS.Claim) in knowledge:
            if not any(provenance.triples((uri, PROV.wasDerivedFrom, None))):
                issues.append("missing_provenance")

        # Low confidence
        conf_obj = next(provenance.objects(uri, SCI_NS.confidence), None)
        if conf_obj is not None:
            try:
                conf = float(str(conf_obj))
                if conf < 0.5:
                    issues.append(f"low_confidence({conf:.2f})")
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

            is_uncertain_status = status.lower() in uncertain_statuses
            is_low_confidence = confidence is not None and confidence < 0.5

            if not is_uncertain_status and not is_low_confidence:
                continue

            text_obj = next(knowledge.objects(uri, SCHEMA_NS.text), None)
            text = str(text_obj) if text_obj else _short_name(str(uri))

            # Sort key: lower confidence = more uncertain; uncertain status adds penalty
            sort_score = confidence if confidence is not None else 0.5
            if is_uncertain_status:
                sort_score -= 1.0

            rows.append(
                {
                    "entity": str(uri),
                    "text": text,
                    "status": status or "-",
                    "confidence": f"{confidence:.2f}" if confidence is not None else "-",
                    "_sort": str(sort_score),
                }
            )

    rows.sort(key=lambda r: float(r["_sort"]))
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
    dataset.serialize(destination=str(graph_path), format="trig")


def _upsert_revision_metadata(dataset: Dataset, graph_path: Path) -> None:
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    for triple in list(provenance.triples((REVISION_URI, None, None))):
        provenance.remove(triple)

    manifest = _build_input_manifest(graph_path=graph_path)
    manifest_json = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    revision_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    provenance.add((REVISION_URI, RDF.type, PROV.Entity))
    provenance.add((REVISION_URI, SCHEMA_NS.name, Literal("graph-revision")))
    provenance.add((REVISION_URI, SCHEMA_NS.dateModified, Literal(revision_time, datatype=XSD.dateTime)))
    provenance.add((REVISION_URI, SCHEMA_NS.text, Literal(manifest_json)))

    preview = dataset.serialize(format="trig")
    preview_text = preview.decode("utf-8") if isinstance(preview, bytes) else str(preview)
    graph_hash = hashlib.sha256(preview_text.encode("utf-8")).hexdigest()
    provenance.add((REVISION_URI, SCHEMA_NS.sha256, Literal(graph_hash)))


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
    include_dirs = ("doc", "specs", "notes", "papers/summaries", "data", "code")
    include_files = ("RESEARCH_PLAN.md", "science.yaml", "CLAUDE.md", "AGENTS.md")

    files: set[Path] = set()
    for file_name in include_files:
        candidate = project_root / file_name
        if candidate.is_file():
            files.add(candidate)

    for dir_name in include_dirs:
        base = project_root / dir_name
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


def _copy_viz_notebook(notebooks_dir: Path) -> None:
    """Copy the bundled viz.py marimo notebook into the notebooks directory."""
    dest = notebooks_dir / "viz.py"
    if dest.exists():
        return
    notebooks_dir.mkdir(parents=True, exist_ok=True)
    template = importlib.resources.files("science_tool.graph").joinpath("viz_template.py")
    with importlib.resources.as_file(template) as src:
        shutil.copy2(src, dest)


def _short_name(uri: str) -> str:
    if uri.startswith(str(PROJECT_NS)):
        return uri.replace(str(PROJECT_NS), "")
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rsplit("/", 1)[-1]
