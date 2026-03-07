"""Export causal inquiry graphs as pgmpy BayesianNetwork scripts."""

from __future__ import annotations

import re
from pathlib import Path

from rdflib import URIRef

from science_tool.graph.store import (
    SCIC_NS,
    SCI_NS,
    _graph_uri,
    _load_dataset,
    _slug,
    get_inquiry,
    shorten_uri,
)


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


def _get_causal_edges_for_inquiry(graph_path: Path, slug: str) -> list[dict]:
    """Collect causal edges (scic:causes, scic:confounds) filtered to inquiry members.

    Returns a list of dicts with keys: subject, predicate, object, pred_type.
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

    causal_graph = dataset.graph(_graph_uri("graph/causal"))

    edges: list[dict] = []
    causal_predicates = {
        SCIC_NS.causes: "causes",
        SCIC_NS.confounds: "confounds",
    }
    for pred_uri, pred_type in causal_predicates.items():
        for s, _p, o in causal_graph.triples((None, pred_uri, None)):
            if s in members and o in members:
                edges.append(
                    {
                        "subject": str(s),
                        "predicate": str(pred_uri),
                        "object": str(o),
                        "pred_type": pred_type,
                    }
                )

    return edges


def export_pgmpy_script(graph_path: Path, slug: str) -> str:
    """Generate a Python script string that builds a pgmpy BayesianNetwork from a causal inquiry.

    The generated script contains pgmpy import statements but this function itself does NOT
    import pgmpy -- it only produces a string.

    Raises:
        ValueError: If the inquiry is not of type ``causal``.
    """
    info = get_inquiry(graph_path, slug)

    if info["inquiry_type"] != "causal":
        raise ValueError(f"pgmpy export only supported for causal inquiries (got '{info['inquiry_type']}')")

    edges = _get_causal_edges_for_inquiry(graph_path, slug)

    treatment_name = _variable_name(info["treatment"]) if info.get("treatment") else None
    outcome_name = _variable_name(info["outcome"]) if info.get("outcome") else None

    # Separate causes vs confounds
    cause_edges = [e for e in edges if e["pred_type"] == "causes"]
    confound_edges = [e for e in edges if e["pred_type"] == "confounds"]

    # Build edge tuples for BayesianNetwork (directed: causes only)
    edge_tuples: list[str] = []
    for e in cause_edges:
        s_name = _variable_name(e["subject"])
        o_name = _variable_name(e["object"])
        edge_tuples.append(f'("{s_name}", "{o_name}")')

    lines: list[str] = []

    # Provenance header
    lines.append(f"# Generated from inquiry: {info['slug']}")
    lines.append(f"# Label: {info['label']}")
    lines.append(f"# Target: {shorten_uri(info['target']) if info.get('target') else 'N/A'}")
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
    edges_str = ", ".join(edge_tuples)
    lines.append(f"model = BayesianNetwork([{edges_str}])")
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

    return "\n".join(lines)
