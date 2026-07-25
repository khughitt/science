from __future__ import annotations

from pathlib import Path

import click

from science_tool.curate.inventory import collect_inventory
from science_tool.output import emit


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
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted inventory to PATH instead of stdout.",
)
def inventory_cmd(
    project_root: Path,
    output_format: str,
    recently_modified_days: int,
    recently_modified_top_k: int,
    output_path: Path | None,
) -> None:
    """Print a deterministic project corpus inventory."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    inventory = collect_inventory(
        project_root,
        recent_days=recently_modified_days,
        recent_top_k=None if recently_modified_top_k <= 0 else recently_modified_top_k,
    )
    payload = inventory.model_dump(mode="json")
    sink = BoundedSink(
        lookup("curate inventory"),
        output_path=output_path,
        command_path="curate inventory",
        complete_via=build_complete_via(click.get_current_context(), output_hint="inventory.json"),
    )
    control_notice = (
        bounded_control_notice(f"wrote the curate inventory to {output_path}")
        if output_path is not None
        else None
    )
    emit(output_format=output_format, payload=payload, render_text=lambda: None, sort_keys=True, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


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
    def _render() -> None:
        click.echo(render_text(report))

    emit(output_format=output_format, payload=report.model_dump(mode="json"), render_text=_render, sort_keys=True)
