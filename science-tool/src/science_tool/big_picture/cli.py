from __future__ import annotations

import click


@click.group("big-picture")
def big_picture_group() -> None:
    """Tools supporting the /science:big-picture command."""


@big_picture_group.command("resolve-questions")
def resolve_questions_cmd() -> None:
    """Placeholder — implemented in Task 8."""
    raise click.ClickException("Not yet implemented")


@big_picture_group.command("validate")
def validate_cmd() -> None:
    """Placeholder — implemented in Task 12."""
    raise click.ClickException("Not yet implemented")
