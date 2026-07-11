from __future__ import annotations

from pathlib import Path

import click
from rdflib import URIRef

from .dataset import _load_dataset
from .identity import _graph_uri, _short_name
from .queries import query_neighborhood


def build_graph_dot(
    graph_path: Path,
    graph_layer: str,
    center: str | None,
    hops: int,
    limit: int,
) -> str:
    if center:
        neighborhood = query_neighborhood(
            graph_path=graph_path,
            center=center,
            hops=hops,
            graph_layer=graph_layer,
            limit=limit,
        )
        if neighborhood.status == "unwired":
            # A center that is not in the graph has no neighbourhood to draw. Emitting an
            # empty digraph would render a nonexistent entity as an isolated node.
            raise click.ClickException(
                f"graph dot did not run ({neighborhood.code}): {neighborhood.reason}"
            )
        rows = neighborhood.rows
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
