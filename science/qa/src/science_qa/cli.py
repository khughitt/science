from __future__ import annotations

import click


@click.group()
def cli() -> None:
    """science-qa command-line interface."""


@cli.command("run")
def run_command() -> None:
    """Run QA checks over a built table (implemented in Task A9)."""
    raise click.ClickException("not yet implemented")
