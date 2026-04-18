from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import click

from science_tool.big_picture.resolver import resolve_questions


@click.group("big-picture")
def big_picture_group() -> None:
    """Tools supporting the /science:big-picture command."""


@big_picture_group.command("resolve-questions")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root (containing specs/, doc/, science.yaml).",
)
def resolve_questions_cmd(project_root: Path) -> None:
    """Emit question→hypothesis resolver output as JSON."""
    results = resolve_questions(project_root)
    payload = {qid: asdict(out) for qid, out in results.items()}
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


@big_picture_group.command("validate")
def validate_cmd() -> None:
    """Placeholder — implemented in Task 12."""
    raise click.ClickException("Not yet implemented")
