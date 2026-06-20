from __future__ import annotations

from pathlib import Path

import click
from rdflib import Dataset

from science_tool.graph.io import (
    PROJECT_NS,
    save_canonical_graph_dataset,
)
from science_tool.graph.io import (
    project_root_from_graph_path as _project_root_from_graph_path,
)

from .constants import GRAPH_LAYERS, INITIAL_GRAPH_TEMPLATE
from .identity import _graph_uri
from .notebooks import _copy_viz_notebook


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


def _load_dataset(graph_path: Path) -> Dataset:
    if not graph_path.exists():
        raise click.ClickException(f"Graph file not found: {graph_path}")

    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    return dataset


def _save_dataset(dataset: Dataset, graph_path: Path) -> None:
    save_graph_dataset(dataset, graph_path)


def save_graph_dataset(dataset: Dataset, graph_path: Path) -> None:
    """Persist a graph dataset with revision metadata refreshed."""
    save_canonical_graph_dataset(
        dataset,
        graph_path,
        preferred_graph_order=[PROJECT_NS[layer] for layer in GRAPH_LAYERS],
    )
