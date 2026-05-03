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
