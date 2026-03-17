"""Export causal inquiry graphs as pgmpy BayesianNetwork scripts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict, cast

from rdflib import URIRef

from science_tool.graph.store import (
    SCHEMA_NS,
    SCI_NS,
    SCIC_NS,
    _collect_evidence_signals,
    _edge_claims,
    _graph_uri,
    _load_dataset,
    _slug,
    _source_strings,
    get_inquiry,
    shorten_uri,
)


class ClaimBundle(TypedDict):
    uri: str
    text: str
    confidence: float | None
    sources: list[str]
    support_count: int
    dispute_count: int


class CausalEdge(TypedDict):
    subject: str
    predicate: str
    object: str
    pred_type: str
    claims: list[ClaimBundle]
    subject_observability: str | None
    object_observability: str | None


def _variable_name(uri: str) -> str:
    """Convert a project URI to a Python-safe variable name.

    Examples:
        ``http://example.org/project/concept/my_var`` -> ``my_var``
        ``http://example.org/project/concept/blood_pressure`` -> ``blood_pressure``
    """
    # Take the last path segment after the final "/"
    short = shorten_uri(uri)
    # shorten_uri returns e.g. "concept/my_var" or the full URI
    if "/" in short:
        short = short.rsplit("/", 1)[-1]
    # Sanitise to a valid Python identifier
    name = re.sub(r"[^a-zA-Z0-9_]", "_", short).strip("_")
    if not name or name[0].isdigit():
        name = f"v_{name}"
    return name


def _get_causal_edges_for_inquiry(graph_path: Path, slug: str) -> list[CausalEdge]:
    """Collect causal edges (scic:causes, scic:confounds) filtered to inquiry members.

    Returns a list of dicts with keys: subject, predicate, object, pred_type,
    claims, subject_observability, object_observability.
    """
    safe_slug = _slug(slug)
    inquiry_uri = URIRef(f"http://example.org/project/inquiry/{safe_slug}")

    dataset = _load_dataset(graph_path)
    inquiry_graph = dataset.graph(inquiry_uri)

    # Collect boundary nodes
    members: set[URIRef] = set()
    for s, _p, o in inquiry_graph.triples((None, SCI_NS.boundaryRole, None)):
        members.add(s)  # type: ignore[arg-type]

    # Collect flow nodes (including scic:causes edges within the inquiry graph)
    flow_predicates = {SCI_NS.feedsInto, SCI_NS.produces, SCIC_NS.causes}
    for s, p, o in inquiry_graph:
        if p in flow_predicates:
            members.add(s)  # type: ignore[arg-type]
            members.add(o)  # type: ignore[arg-type]

    # Collect observability for each member variable from graph/knowledge
    knowledge_graph = dataset.graph(_graph_uri("graph/knowledge"))
    observability: dict[str, str | None] = {}
    for member_uri in members:
        obs_obj = next(knowledge_graph.objects(member_uri, SCI_NS.observability), None)
        observability[str(member_uri)] = str(obs_obj) if obs_obj is not None else None

    # Collect relation claims attached directly to causal edges.
    provenance_graph = dataset.graph(_graph_uri("graph/provenance"))
    causal_graph = dataset.graph(_graph_uri("graph/causal"))
    edge_map: dict[tuple[str, str, str], CausalEdge] = {}
    causal_predicates = {
        SCIC_NS.causes: "causes",
        SCIC_NS.confounds: "confounds",
    }
    for graph in (inquiry_graph, causal_graph):
        for pred_uri, pred_type in causal_predicates.items():
            for s, _p, o in graph.triples((None, pred_uri, None)):
                if not isinstance(s, URIRef) or not isinstance(o, URIRef):
                    continue
                if s not in members or o not in members:
                    continue

                key = (str(s), str(pred_uri), str(o))
                edge = edge_map.setdefault(
                    key,
                    {
                        "subject": str(s),
                        "predicate": str(pred_uri),
                        "object": str(o),
                        "pred_type": pred_type,
                        "claims": [],
                        "subject_observability": observability.get(str(s)),
                        "object_observability": observability.get(str(o)),
                    },
                )

                existing_claim_uris = {claim["uri"] for claim in edge["claims"]}
                for claim_uri in _edge_claims(graph, s, pred_uri, o):
                    if str(claim_uri) in existing_claim_uris:
                        continue
                    text_obj = next(knowledge_graph.objects(claim_uri, SCHEMA_NS.text), None)
                    confidence_obj = next(provenance_graph.objects(claim_uri, SCI_NS.confidence), None)
                    evidence = _collect_evidence_signals(knowledge_graph, provenance_graph, claim_uri)
                    claim_bundle: ClaimBundle = {
                        "uri": str(claim_uri),
                        "text": str(text_obj) if text_obj is not None else shorten_uri(str(claim_uri)),
                        "confidence": float(str(confidence_obj)) if confidence_obj is not None else None,
                        "sources": _source_strings(provenance_graph, claim_uri),
                        "support_count": cast(int, evidence["support_count"]),
                        "dispute_count": cast(int, evidence["dispute_count"]),
                    }
                    edge["claims"].append(claim_bundle)

    return list(edge_map.values())


def export_pgmpy_script(graph_path: Path, slug: str) -> str:
    """Generate a Python script string that builds a pgmpy BayesianNetwork from a causal inquiry.

    The generated script contains pgmpy import statements but this function itself does NOT
    import pgmpy -- it only produces a string.

    Raises:
        ValueError: If the inquiry is not of type ``causal``.
    """
    info = get_inquiry(graph_path, slug)

    if info.get("inquiry_type", "general") != "causal":
        raise ValueError(f"pgmpy export only supported for causal inquiries (got '{info.get('inquiry_type')}')")

    edges = _get_causal_edges_for_inquiry(graph_path, slug)

    # Query revision hash from provenance graph
    dataset = _load_dataset(graph_path)
    provenance_graph = dataset.graph(_graph_uri("graph/provenance"))
    revision_uri = URIRef("http://example.org/project/graph_revision")
    revision_hash = str(next(provenance_graph.objects(revision_uri, SCHEMA_NS.sha256), "unknown"))

    treatment = info["treatment"]
    outcome = info["outcome"]
    treatment_name = _variable_name(treatment) if treatment else None
    outcome_name = _variable_name(outcome) if outcome else None

    # Separate causes vs confounds
    cause_edges = [e for e in edges if e["pred_type"] == "causes"]
    confound_edges = [e for e in edges if e["pred_type"] == "confounds"]

    # Build edge tuples for BayesianNetwork (directed: causes only)
    edge_tuples: list[str] = []
    for e in cause_edges:
        s_name = _variable_name(e["subject"])
        o_name = _variable_name(e["object"])
        comment_parts: list[str] = []
        if e.get("claims"):
            claim_summaries: list[str] = []
            for claim in e["claims"]:
                claim_parts = [f'claim: "{claim["text"]}"']
                if claim["confidence"] is not None:
                    claim_parts.append(f"confidence: {claim['confidence']}")
                claim_parts.append(f"supports: {claim['support_count']}")
                claim_parts.append(f"disputes: {claim['dispute_count']}")
                if claim["sources"]:
                    claim_parts.append(
                        "sources: " + ", ".join(shorten_uri(source) for source in claim["sources"])
                    )
                claim_summaries.append(", ".join(claim_parts))
            comment_parts.append(" | ".join(claim_summaries))
        comment = f"  # {', '.join(comment_parts)}" if comment_parts else ""
        edge_tuples.append(f'("{s_name}", "{o_name}"),{comment}')

    lines: list[str] = []

    # Provenance header
    lines.append(f"# Generated from inquiry: {info['slug']}")
    lines.append(f"# Label: {info['label']}")
    lines.append(f"# Target: {shorten_uri(info['target']) if info.get('target') else 'N/A'}")
    lines.append(f"# Revision: {revision_hash}")
    if treatment_name:
        lines.append(f"# Treatment: {treatment_name}")
    if outcome_name:
        lines.append(f"# Outcome: {outcome_name}")
    lines.append("")

    # Imports
    lines.append("from pgmpy.models import BayesianNetwork")
    lines.append("from pgmpy.inference import CausalInference")
    lines.append("")

    # Build model
    edges_str = "\n    ".join(edge_tuples)
    lines.append(f"model = BayesianNetwork([\n    {edges_str}\n])")
    lines.append("")

    # Confounders as comments
    if confound_edges:
        lines.append("# Confounders (not directly representable as directed edges):")
        for e in confound_edges:
            s_name = _variable_name(e["subject"])
            o_name = _variable_name(e["object"])
            lines.append(f"#   {s_name} <-> {o_name}")
        lines.append("")

    # Inference
    lines.append("ci = CausalInference(model)")
    if treatment_name and outcome_name:
        lines.append(f'adj_sets = ci.get_all_backdoor_adjustment_sets("{treatment_name}", "{outcome_name}")')
        lines.append('print("Backdoor adjustment sets:", adj_sets)')
    lines.append("")

    # TODO section for latent variables and unsupported edges
    latent_vars: list[str] = []
    for e in edges:
        if e.get("subject_observability") == "latent":
            latent_vars.append(_variable_name(e["subject"]))
        if e.get("object_observability") == "latent":
            latent_vars.append(_variable_name(e["object"]))
    latent_vars = sorted(set(latent_vars))

    edges_without_claims = [
        f"{_variable_name(e['subject'])} -> {_variable_name(e['object'])}" for e in cause_edges if not e.get("claims")
    ]

    if latent_vars or edges_without_claims:
        lines.append("# TODO:")
        for lv in latent_vars:
            lines.append(f"#   - Variable '{lv}' is latent (unobserved) — cannot be directly measured")
        for ec in edges_without_claims:
            lines.append(f"#   - Edge {ec} has no attached relation claim")
        lines.append("")

    return "\n".join(lines)
