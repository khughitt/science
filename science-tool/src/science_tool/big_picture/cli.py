from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import click

from science_tool.big_picture.resolver import resolve_questions
from science_tool.big_picture.validator import validate_rollup_file, validate_synthesis_file


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
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root.",
)
def validate_cmd(project_root: Path) -> None:
    """Validate generated big-picture synthesis files in this project."""
    synthesis_dir = project_root / "doc" / "reports" / "synthesis"
    rollup_path = project_root / "doc" / "reports" / "synthesis.md"

    issues = []
    if synthesis_dir.is_dir():
        for path in sorted(synthesis_dir.glob("*.md")):
            if path.name.startswith("_"):
                continue
            issues.extend(validate_synthesis_file(path, project_root=project_root))
    if rollup_path.is_file():
        issues.extend(validate_rollup_file(rollup_path, project_root=project_root))

    for issue in issues:
        click.echo(f"[{issue.kind}] {issue.path.name}: {issue.message}")

    if issues:
        raise click.exceptions.Exit(code=1)
