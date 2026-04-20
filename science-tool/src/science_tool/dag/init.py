"""Scaffold a new DAG stub: <slug>.dot + <slug>.edges.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml


def init_dag(dag_dir: Path, slug: str, label: str | None = None) -> None:
    """Scaffold ``<slug>.dot`` + ``<slug>.edges.yaml`` under *dag_dir*.

    Raises ``FileExistsError`` if either file already exists.

    Parameters
    ----------
    dag_dir:
        Directory where DAG files live (e.g. ``doc/figures/dags/``).
    slug:
        Kebab-case identifier for the new DAG (e.g. ``h3-new-hypothesis``).
    label:
        Optional human-readable label. Defaults to the slug if omitted.
    """
    dot_path = dag_dir / f"{slug}.dot"
    yaml_path = dag_dir / f"{slug}.edges.yaml"

    if dot_path.exists():
        raise FileExistsError(f"{dot_path} already exists; refusing to overwrite.")
    if yaml_path.exists():
        raise FileExistsError(f"{yaml_path} already exists; refusing to overwrite.")

    effective_label = label if label is not None else slug
    graph_name = slug.replace("-", "_")
    slug_title = effective_label

    dot_content = f"""\
// {slug} — {effective_label}
digraph {graph_name} {{
  rankdir=TB;
  labelloc="t";
  label=<<b>{slug_title}</b>>;
  node [shape=box, style="rounded,filled", fillcolor="#f0f0f0", fontsize=10];
  edge [fontsize=9];

  // Add nodes and edges here.
}}
"""
    dot_path.write_text(dot_content)

    edges_data: dict = {
        "dag": slug,
        "source_dot": f"doc/figures/dags/{slug}.dot",
        "edges": [],
    }
    yaml_path.write_text(yaml.dump(edges_data, default_flow_style=False, sort_keys=False))
