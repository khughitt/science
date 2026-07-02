from __future__ import annotations

from pathlib import Path

import click

from science_tool.distill.openalex import distill_openalex
from science_tool.distill.pykeen_source import distill_pykeen


@click.group("distill")
def distill_group() -> None:
    """Distill public knowledge graphs into Turtle snapshots."""


@distill_group.command("openalex")
@click.option("--level", type=click.Choice(("subfields", "topics")), default="subfields", show_default=True)
@click.option("--output", "output_path", default=None, type=click.Path(path_type=Path))
@click.option("--cache-path", default=None, type=click.Path(path_type=Path))
def distill_openalex_cmd(level: str, output_path: Path | None, cache_path: Path | None) -> None:
    """Fetch OpenAlex science hierarchy and write Turtle snapshot."""

    result = distill_openalex(level=level, output_path=output_path, cache_path=cache_path)
    click.echo(f"Wrote OpenAlex snapshot ({level}) to {result}")


@distill_group.command("pykeen")
@click.argument("dataset_name")
@click.option("--budget", type=int, default=None)
@click.option("--output", "output_path", default=None, type=click.Path(path_type=Path))
def distill_pykeen_cmd(dataset_name: str, budget: int | None, output_path: Path | None) -> None:
    """Distill a PyKEEN dataset into a Turtle snapshot."""

    result = distill_pykeen(dataset_name=dataset_name, budget=budget, output_path=output_path)
    click.echo(f"Wrote {dataset_name} snapshot to {result}")
