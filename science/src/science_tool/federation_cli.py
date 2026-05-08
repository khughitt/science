"""CLI subgroup for federation v1.0."""

from __future__ import annotations

from pathlib import Path

import click

from science_tool.project_config import ProjectRole, load_project_config


@click.group(name="federation")
def federation_group() -> None:
    """Federation operations."""


@federation_group.command("validate")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def federation_validate(project_root: Path) -> None:
    """Validate meta's children manifest against child parent back-references."""
    from science_tool.federation import validate_federation  # noqa: PLC0415

    root = Path.cwd() if str(project_root) == "." else project_root
    cfg = load_project_config(root)
    if cfg.role != ProjectRole.META:
        raise click.ClickException(f"{root} is not a meta project (role={cfg.role!r})")

    issues = validate_federation(root)
    if not issues:
        click.echo("ok: federation consistent")
        return

    for issue in issues:
        click.echo(f"{issue.kind}: child={issue.child_id}: {issue.detail}", err=True)
    raise click.exceptions.Exit(1)


@federation_group.command("status")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def federation_status(project_root: Path) -> None:
    """Render a cross-project status rollup for a meta umbrella."""
    from science_tool.federation_status import render_federated_status  # noqa: PLC0415

    root = Path.cwd() if str(project_root) == "." else project_root
    try:
        rendered = render_federated_status(root)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(rendered)
