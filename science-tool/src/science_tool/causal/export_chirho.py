"""Export a causal inquiry to a ChiRho/Pyro scaffold script."""

from __future__ import annotations

from collections import deque
from pathlib import Path

from science_tool.causal.export_pgmpy import _get_causal_edges_for_inquiry, _variable_name
from science_tool.graph.store import get_inquiry


def _topological_sort(edges: list[dict[str, str]]) -> list[str]:
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


def _get_parents(var_name: str, edges: list[dict[str, str]]) -> list[str]:
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
    treatment = info.get("treatment")
    outcome = info.get("outcome")

    treatment_name = _variable_name(treatment) if treatment else "TREATMENT"
    outcome_name = _variable_name(outcome) if outcome else "OUTCOME"

    sorted_vars = _topological_sort(edges)

    lines: list[str] = []
    lines.append(f"# Generated from inquiry: {slug}")
    lines.append(f"# Label: {info['label']}")
    lines.append(f"# Target: {info['target']}")
    lines.append(f"# Treatment: {treatment_name}")
    lines.append(f"# Outcome: {outcome_name}")
    lines.append("#")
    lines.append("# TODO: Replace placeholder distributions with appropriate priors")
    lines.append("# TODO: Add observed data conditioning")
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
        elif len(parents) == 1:
            lines.append(f'    {var} = pyro.sample("{var}", dist.Normal({parents[0]}, 1.0))  # caused by {parents[0]}')
        else:
            parent_sum = " + ".join(parents)
            parent_list = ", ".join(parents)
            lines.append(f'    {var} = pyro.sample("{var}", dist.Normal({parent_sum}, 1.0))  # caused by {parent_list}')

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
