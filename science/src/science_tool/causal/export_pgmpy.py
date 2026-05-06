"""Export causal inquiry graphs as pgmpy BayesianNetwork scripts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import NotRequired, TypedDict, cast

from rdflib import URIRef

from science_tool.graph.store import (
    FalsificationRecord,
    PropositionEvidenceLine,
    PropositionInteractionTerm,
    PropositionPhase1Metadata,
    PropositionEvidenceSemantics,
    SCHEMA_NS,
    SCI_NS,
    SCIC_NS,
    _collect_evidence_signals,
    _edge_claims,
    _graph_uri,
    _load_proposition_bridge_hypotheses,
    _load_proposition_evidence_semantics,
    _load_proposition_falsifications,
    _load_proposition_interaction_terms,
    _load_proposition_phase1_metadata,
    _load_proposition_pre_registrations,
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
    claim_layer: NotRequired[str]
    supports_scope: NotRequired[str]
    compositional_status: NotRequired[str]
    compositional_method: NotRequired[str]
    compositional_note: NotRequired[str]
    platform_pattern: NotRequired[str]
    dataset_effects: NotRequired[dict[str, float]]
    evidence_lines: NotRequired[list[PropositionEvidenceLine]]
    measurement_model: NotRequired[dict[str, object]]
    rival_model_packet: NotRequired[dict[str, object]]
    falsifications: NotRequired[list[FalsificationRecord]]
    statistical_support: NotRequired[str]
    mechanistic_support: NotRequired[str]
    replication_scope: NotRequired[str]
    claim_status: NotRequired[str]
    identification_strength: NotRequired[str]
    proxy_directness: NotRequired[str]
    independence_group: NotRequired[str]
    evidence_role: NotRequired[str]
    pre_registrations: NotRequired[list[str]]
    interaction_terms: NotRequired[list[PropositionInteractionTerm]]
    bridge_between: NotRequired[list[str]]


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
                    _apply_phase1_metadata_to_claim_bundle(
                        claim_bundle,
                        _load_proposition_phase1_metadata(provenance_graph, claim_uri),
                    )
                    _apply_evidence_semantics_to_claim_bundle(
                        claim_bundle,
                        _load_proposition_evidence_semantics(provenance_graph, claim_uri),
                    )
                    pre_registrations = _load_proposition_pre_registrations(provenance_graph, claim_uri)
                    if pre_registrations:
                        claim_bundle["pre_registrations"] = pre_registrations
                    interaction_terms = _load_proposition_interaction_terms(provenance_graph, claim_uri)
                    if interaction_terms:
                        claim_bundle["interaction_terms"] = interaction_terms
                    bridge_between = _load_proposition_bridge_hypotheses(provenance_graph, claim_uri)
                    if bridge_between:
                        claim_bundle["bridge_between"] = bridge_between
                    falsifications = _load_proposition_falsifications(knowledge_graph, claim_uri)
                    if falsifications:
                        claim_bundle["falsifications"] = falsifications
                    edge["claims"].append(claim_bundle)

    return list(edge_map.values())


def _apply_phase1_metadata_to_claim_bundle(
    bundle: ClaimBundle,
    metadata: PropositionPhase1Metadata,
) -> None:
    if "claim_layer" in metadata:
        bundle["claim_layer"] = metadata["claim_layer"]
    if "supports_scope" in metadata:
        bundle["supports_scope"] = metadata["supports_scope"]
    if "compositional_status" in metadata:
        bundle["compositional_status"] = metadata["compositional_status"]
    if "compositional_method" in metadata:
        bundle["compositional_method"] = metadata["compositional_method"]
    if "compositional_note" in metadata:
        bundle["compositional_note"] = metadata["compositional_note"]
    if "platform_pattern" in metadata:
        bundle["platform_pattern"] = metadata["platform_pattern"]
    if "dataset_effects" in metadata:
        bundle["dataset_effects"] = metadata["dataset_effects"]
    if "evidence_lines" in metadata:
        bundle["evidence_lines"] = metadata["evidence_lines"]
    if "measurement_model" in metadata:
        bundle["measurement_model"] = metadata["measurement_model"]
    if "rival_model_packet" in metadata:
        bundle["rival_model_packet"] = metadata["rival_model_packet"]


def _apply_evidence_semantics_to_claim_bundle(
    bundle: ClaimBundle,
    semantics: PropositionEvidenceSemantics,
) -> None:
    if "statistical_support" in semantics:
        bundle["statistical_support"] = semantics["statistical_support"]
    if "mechanistic_support" in semantics:
        bundle["mechanistic_support"] = semantics["mechanistic_support"]
    if "replication_scope" in semantics:
        bundle["replication_scope"] = semantics["replication_scope"]
    if "claim_status" in semantics:
        bundle["claim_status"] = semantics["claim_status"]
    if "identification_strength" in semantics:
        bundle["identification_strength"] = semantics["identification_strength"]
    if "proxy_directness" in semantics:
        bundle["proxy_directness"] = semantics["proxy_directness"]
    if "independence_group" in semantics:
        bundle["independence_group"] = semantics["independence_group"]
    if "evidence_role" in semantics:
        bundle["evidence_role"] = semantics["evidence_role"]


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
                    claim_parts.append("sources: " + ", ".join(shorten_uri(source) for source in claim["sources"]))
                compositional_status = claim.get("compositional_status")
                if compositional_status:
                    compositional_method = claim.get("compositional_method")
                    if compositional_method:
                        claim_parts.append(f"compositional: {compositional_status} ({compositional_method})")
                    else:
                        claim_parts.append(f"compositional: {compositional_status}")
                platform_pattern = claim.get("platform_pattern")
                if platform_pattern:
                    claim_parts.append(f"platform: {platform_pattern}")
                dataset_effects = claim.get("dataset_effects")
                if dataset_effects:
                    effect_summary = ", ".join(
                        f"{dataset}={effect:.2f}" for dataset, effect in cast(dict[str, float], dataset_effects).items()
                    )
                    claim_parts.append(f"dataset_effects: {effect_summary}")
                evidence_lines = claim.get("evidence_lines")
                if evidence_lines:
                    claim_parts.append(f"evidence_lines: {len(cast(list[dict[str, object]], evidence_lines))}")
                statistical_support = claim.get("statistical_support")
                if statistical_support:
                    claim_parts.append(f"statistical_support: {statistical_support}")
                mechanistic_support = claim.get("mechanistic_support")
                if mechanistic_support:
                    claim_parts.append(f"mechanistic_support: {mechanistic_support}")
                replication_scope = claim.get("replication_scope")
                if replication_scope:
                    claim_parts.append(f"replication_scope: {replication_scope}")
                claim_status = claim.get("claim_status")
                if claim_status:
                    claim_parts.append(f"claim_status: {claim_status}")
                pre_registrations = claim.get("pre_registrations")
                if pre_registrations:
                    claim_parts.append(f"pre_registrations: {len(cast(list[str], pre_registrations))}")
                    claim_parts.append("pre_registered_in: " + ", ".join(cast(list[str], pre_registrations)))
                interaction_terms = claim.get("interaction_terms")
                if interaction_terms:
                    term_list = cast(list[dict[str, str]], interaction_terms)
                    claim_parts.append(f"interaction_terms: {len(term_list)}")
                    claim_parts.append(
                        "modified_by: " + ", ".join(f"{term['modifier']}({term['effect']})" for term in term_list)
                    )
                bridge_between = claim.get("bridge_between")
                if bridge_between:
                    claim_parts.append(f"bridge_between: {len(cast(list[str], bridge_between))}")
                    claim_parts.append("bridges: " + ", ".join(cast(list[str], bridge_between)))
                falsifications = claim.get("falsifications")
                if falsifications:
                    claim_parts.append(f"falsifications: {len(cast(list[dict[str, str]], falsifications))}")
                    latest_decision = cast(list[dict[str, str]], falsifications)[-1].get("decision")
                    if latest_decision:
                        claim_parts.append(f"latest_decision: {latest_decision}")
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
