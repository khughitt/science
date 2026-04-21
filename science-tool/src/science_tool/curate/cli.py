from __future__ import annotations

import json
from pathlib import Path

import click


@click.group("curate")
def curate_group() -> None:
    """Tools supporting the /science:curate command."""


@curate_group.command("inventory")
@click.option("--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True)
@click.option("--format", "output_format", type=click.Choice(["json"]), default="json", show_default=True)
def inventory_cmd(project_root: Path, output_format: str) -> None:
    """Print a deterministic project corpus inventory."""
    payload = {"project_root": str(project_root), "artifact_counts": {}}
    click.echo(json.dumps(payload, indent=2, sort_keys=True))
