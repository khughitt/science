"""`science belief` command group — derived belief scalar and snapshots."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import click

from science_tool.graph import belief_profile, belief_snapshot
from science_tool.graph.store import DEFAULT_GRAPH_PATH
from science_tool.output import OUTPUT_FORMATS, emit_query_rows


@click.group("belief")
def belief_group() -> None:
    """Derived belief scalar and append-only snapshots."""


@belief_group.command("snapshot")
@click.option(
    "--path",
    "graph_path",
    default=str(DEFAULT_GRAPH_PATH),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option("--as-of", "as_of", default=None, help="Snapshot date YYYY-MM-DD (default: today).")
def belief_snapshot_cmd(graph_path: Path, as_of: str | None) -> None:
    """Append per-claim belief snapshots to knowledge/belief-snapshots.jsonl."""
    from science_tool.graph.io import project_root_from_graph_path

    as_of_value = as_of or date.today().isoformat()
    records = belief_snapshot.make_snapshots(graph_path, as_of=as_of_value)
    out_path = project_root_from_graph_path(graph_path) / "knowledge" / "belief-snapshots.jsonl"
    added = belief_snapshot.append_snapshots(out_path, records)
    click.echo(f"belief snapshot {as_of_value}: {len(records)} claims, {added} new rows -> {out_path}")


def _belief_profile_table_row(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row["evidence"]
    caps = row["caps"]
    cap_labels = [name for name, active in caps.items() if active]
    return {
        "entity": row["entity"],
        "kind": row["kind"],
        "belief_state": row["belief_state"],
        "contested": "yes" if row["contested"] else "no",
        "labels": ", ".join(row["epistemic_labels"]) or "-",
        "support": evidence["support_count"],
        "dispute": evidence["dispute_count"],
        "diagnostic": "-" if evidence["diagnostic_count"] is None else evidence["diagnostic_count"],
        "sources": evidence["source_count"],
        "empirical": "yes" if evidence["has_empirical_data"] else "no",
        "caps": ", ".join(cap_labels) or "-",
        "freshness": row["freshness_state"] or "-",
        "label": row["label"],
    }


@belief_group.command("profile")
@click.option(
    "--path",
    "graph_path",
    default=str(DEFAULT_GRAPH_PATH),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
@click.option(
    "--kind",
    "kinds",
    multiple=True,
    type=click.Choice(belief_profile.SUPPORTED_KINDS),
    help="Entity kind filter; repeatable.",
)
@click.option(
    "--label",
    "labels",
    multiple=True,
    type=click.Choice(belief_profile.PROFILE_LABELS),
    help="Epistemic label filter; repeatable with AND semantics.",
)
@click.option("--all", "include_all", is_flag=True, help="Include every supported belief-bearing entity.")
def belief_profile_cmd(
    graph_path: Path,
    output_format: str,
    kinds: tuple[str, ...],
    labels: tuple[str, ...],
    include_all: bool,
) -> None:
    """List derived epistemic profiles for belief-bearing entities."""
    rows = belief_profile.make_profiles(
        graph_path,
        include_all=include_all,
        kinds=kinds,
        labels=labels,
    )
    emit_rows = rows if output_format == "json" else [_belief_profile_table_row(row) for row in rows]
    emit_query_rows(
        output_format=output_format,
        title="Belief Profile",
        columns=[
            ("entity", "Entity"),
            ("kind", "Kind"),
            ("belief_state", "Belief"),
            ("contested", "Contested"),
            ("labels", "Labels"),
            ("support", "Support"),
            ("dispute", "Dispute"),
            ("diagnostic", "Diagnostic"),
            ("sources", "Sources"),
            ("empirical", "Empirical"),
            ("caps", "Caps"),
            ("freshness", "Freshness"),
            ("label", "Label"),
        ],
        rows=emit_rows,
        meta={
            "count": len(rows),
            "include_all": include_all,
            "kinds": list(kinds),
            "labels": list(labels),
        },
    )
