"""Export a causal inquiry to a ChiRho/Pyro scaffold script."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Sequence

from rdflib import URIRef

from science_tool.causal.export_pgmpy import CausalEdge, ClaimBundle, _get_causal_edges_for_inquiry, _variable_name
from science_tool.graph.store import (
    SCHEMA_NS,
    _graph_uri,
    _load_dataset,
    get_inquiry,
    shorten_uri,
)


def _topological_sort(edges: Sequence[CausalEdge]) -> list[str]:
    """Topological sort of variable names derived from causal edges."""
    graph: dict[str, list[str]] = {}
    in_degree: dict[str, int] = {}
    all_nodes: set[str] = set()

    for edge in edges:
        if edge["pred_type"] != "causes":
            continue
        s = _variable_name(edge["subject"])
        t = _variable_name(edge["object"])
        all_nodes.add(s)
        all_nodes.add(t)
        graph.setdefault(s, []).append(t)
        in_degree.setdefault(s, 0)
        in_degree[t] = in_degree.get(t, 0) + 1

    queue = deque(n for n in sorted(all_nodes) if in_degree.get(n, 0) == 0)
    result: list[str] = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in sorted(graph.get(node, [])):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    return result


def _get_parents(var_name: str, edges: Sequence[CausalEdge]) -> list[str]:
    """Get parent variable names (causes) for a variable."""
    return [
        _variable_name(e["subject"])
        for e in edges
        if _variable_name(e["object"]) == var_name and e["pred_type"] == "causes"
    ]


def export_chirho_script(graph_path: Path, slug: str) -> str:
    """Generate a ChiRho/Pyro scaffold script from a causal inquiry.

    The generated script contains pyro/chirho import statements but this function itself
    does NOT import pyro or chirho -- it only produces a string.

    Raises:
        ValueError: If the inquiry is not of type ``causal``.
    """
    info = get_inquiry(graph_path, slug)

    if info.get("inquiry_type", "general") != "causal":
        raise ValueError(f"ChiRho export only supported for causal inquiries (got '{info.get('inquiry_type')}')")

    edges = _get_causal_edges_for_inquiry(graph_path, slug)

    # Query revision hash from provenance graph
    dataset = _load_dataset(graph_path)
    provenance_graph = dataset.graph(_graph_uri("graph/provenance"))
    revision_uri = URIRef("http://example.org/project/graph_revision")
    revision_hash = str(next(provenance_graph.objects(revision_uri, SCHEMA_NS.sha256), "unknown"))

    treatment = info.get("treatment")
    if not isinstance(treatment, str):
        treatment = None
    outcome = info.get("outcome")
    if not isinstance(outcome, str):
        outcome = None

    treatment_name = _variable_name(treatment) if treatment else "TREATMENT"
    outcome_name = _variable_name(outcome) if outcome else "OUTCOME"

    sorted_vars = _topological_sort(edges)

    # Build per-edge claim lookup to preserve provenance for each parent -> child edge.
    edge_claims: dict[tuple[str, str], list[ClaimBundle]] = {}
    for e in edges:
        if e["pred_type"] == "causes" and e.get("claims"):
            s_name = _variable_name(e["subject"])
            o_name = _variable_name(e["object"])
            edge_claims[(s_name, o_name)] = list(e["claims"])

    # Collect latent variables
    latent_vars: set[str] = set()
    for e in edges:
        if e.get("subject_observability") == "latent":
            latent_vars.add(_variable_name(e["subject"]))
        if e.get("object_observability") == "latent":
            latent_vars.add(_variable_name(e["object"]))

    lines: list[str] = []
    lines.append(f"# Generated from inquiry: {slug}")
    lines.append(f"# Label: {info['label']}")
    lines.append(f"# Target: {info['target']}")
    lines.append(f"# Revision: {revision_hash}")
    lines.append(f"# Treatment: {treatment_name}")
    lines.append(f"# Outcome: {outcome_name}")
    lines.append("#")
    lines.append("# TODO: Replace placeholder distributions with appropriate priors")
    lines.append("# TODO: Add observed data conditioning")
    ungrounded_edges = [
        f"{_variable_name(edge['subject'])} -> {_variable_name(edge['object'])}"
        for edge in edges
        if edge["pred_type"] == "causes" and not edge.get("claims")
    ]
    if latent_vars:
        lines.append("# TODO: Latent (unobserved) variables — cannot condition on data directly:")
        for lv in sorted(latent_vars):
            lines.append(f"#   - {lv}")
    if ungrounded_edges:
        lines.append("# TODO: Ungrounded causal edges:")
        for edge in ungrounded_edges:
            lines.append(f"#   - Edge {edge} has no attached relation claim")
    lines.append("")
    lines.append("import torch")
    lines.append("import pyro")
    lines.append("import pyro.distributions as dist")
    lines.append("from chirho.interventional.handlers import do")
    lines.append("from pyro.infer import Predictive")
    lines.append("")
    lines.append("")
    lines.append("def causal_model():")
    lines.append('    """Structural causal model."""')

    for var in sorted_vars:
        parents = _get_parents(var, edges)
        if not parents:
            lines.append(f'    {var} = pyro.sample("{var}", dist.Normal(0.0, 1.0))  # root')
        else:
            if len(parents) == 1:
                comment = f"caused by {parents[0]}"
            else:
                comment = f"caused by {', '.join(parents)}"
            edge_comments: list[str] = []
            for parent in parents:
                claims_for_edge = edge_claims.get((parent, var), [])
                if not claims_for_edge:
                    continue
                claim_comments: list[str] = []
                for claim in claims_for_edge:
                    prov_parts: list[str] = []
                    if claim["confidence"] is not None:
                        prov_parts.append(f"confidence: {claim['confidence']}")
                    prov_parts.append(f"supports: {claim['support_count']}")
                    prov_parts.append(f"disputes: {claim['dispute_count']}")
                    if claim["sources"]:
                        prov_parts.append("sources: " + ", ".join(shorten_uri(source) for source in claim["sources"]))
                    compositional_status = claim.get("compositional_status")
                    if compositional_status:
                        compositional_method = claim.get("compositional_method")
                        if compositional_method:
                            prov_parts.append(f"compositional: {compositional_status} ({compositional_method})")
                        else:
                            prov_parts.append(f"compositional: {compositional_status}")
                    platform_pattern = claim.get("platform_pattern")
                    if platform_pattern:
                        prov_parts.append(f"platform: {platform_pattern}")
                    dataset_effects = claim.get("dataset_effects")
                    if dataset_effects:
                        effect_summary = ", ".join(
                            f"{dataset}={effect:.2f}" for dataset, effect in dataset_effects.items()
                        )
                        prov_parts.append(f"dataset_effects: {effect_summary}")
                    evidence_lines = claim.get("evidence_lines")
                    if evidence_lines:
                        prov_parts.append(f"evidence_lines: {len(evidence_lines)}")
                    statistical_support = claim.get("statistical_support")
                    if statistical_support:
                        prov_parts.append(f"statistical_support: {statistical_support}")
                    mechanistic_support = claim.get("mechanistic_support")
                    if mechanistic_support:
                        prov_parts.append(f"mechanistic_support: {mechanistic_support}")
                    replication_scope = claim.get("replication_scope")
                    if replication_scope:
                        prov_parts.append(f"replication_scope: {replication_scope}")
                    claim_status = claim.get("claim_status")
                    if claim_status:
                        prov_parts.append(f"claim_status: {claim_status}")
                    pre_registrations = claim.get("pre_registrations")
                    if pre_registrations:
                        prov_parts.append(f"pre_registrations: {len(pre_registrations)}")
                        prov_parts.append("pre_registered_in: " + ", ".join(pre_registrations))
                    falsifications = claim.get("falsifications")
                    if falsifications:
                        prov_parts.append(f"falsifications: {len(falsifications)}")
                        latest_decision = falsifications[-1].get("decision")
                        if latest_decision:
                            prov_parts.append(f"latest_decision: {latest_decision}")
                    if prov_parts:
                        claim_comments.append(", ".join(prov_parts))
                if claim_comments:
                    edge_comments.append(f"{parent}: " + " | ".join(claim_comments))
            if edge_comments:
                comment += " | " + "; ".join(edge_comments)
            parent_sum = " + ".join(parents)
            lines.append(f'    {var} = pyro.sample("{var}", dist.Normal({parent_sum}, 1.0))  # {comment}')

    lines.append(f"    return {outcome_name}")
    lines.append("")
    lines.append("")
    lines.append(f"# Interventional query: P({outcome_name} | do({treatment_name}=1.0))")
    lines.append(f'intervened_model = do(causal_model, actions={{"{treatment_name}": torch.tensor(1.0)}})')
    lines.append("predictive = Predictive(intervened_model, num_samples=1000)")
    lines.append("samples = predictive()")
    lines.append(f'print("{outcome_name} under intervention:", samples["{outcome_name}"].mean().item())')
    lines.append("")

    return "\n".join(lines) + "\n"
