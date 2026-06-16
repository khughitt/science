from __future__ import annotations

import json
from pathlib import Path

import click

from science_tool.curate.inventory import collect_inventory


@click.group("curate")
def curate_group() -> None:
    """Tools supporting the /science:curate command."""


@curate_group.command("inventory")
@click.option("--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True)
@click.option("--format", "output_format", type=click.Choice(["json"]), default="json", show_default=True)
@click.option(
    "--recently-modified-days",
    type=int,
    default=7,
    show_default=True,
    help="Window (days) for the recently_modified signal.",
)
@click.option(
    "--recently-modified-top-k",
    type=int,
    default=20,
    show_default=True,
    help="Cap recently_modified to the K most-recent entries; pass 0 to disable.",
)
def inventory_cmd(
    project_root: Path,
    output_format: str,
    recently_modified_days: int,
    recently_modified_top_k: int,
) -> None:
    """Print a deterministic project corpus inventory."""
    inventory = collect_inventory(
        project_root,
        recent_days=recently_modified_days,
        recent_top_k=None if recently_modified_top_k <= 0 else recently_modified_top_k,
    )
    payload = inventory.model_dump(mode="json")
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


@curate_group.command("consolidation-candidates")
@click.option("--project-root", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path("."), show_default=True)
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json", show_default=True)
@click.option("--related-jaccard", type=float, default=0.7, show_default=True, help="Jaccard threshold for the related-overlap signal.")
@click.option("--min-cluster-size", type=int, default=2, show_default=True, help="Minimum members for a reported cluster.")
@click.option("--max-cluster-size", type=int, default=15, show_default=True, help="Suppress (but count) qualifying clusters larger than this.")
def consolidation_candidates_cmd(
    project_root: Path,
    output_format: str,
    related_jaccard: float,
    min_cluster_size: int,
    max_cluster_size: int,
) -> None:
    """Report consolidation candidates (read-only; superseded-lineage + semantic)."""
    from science_tool.consolidation_candidates import detect_consolidation_candidates, render_text

    report = detect_consolidation_candidates(
        project_root,
        related_jaccard=related_jaccard,
        min_cluster_size=min_cluster_size,
        max_cluster_size=max_cluster_size,
    )
    if output_format == "json":
        click.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        click.echo(render_text(report))
