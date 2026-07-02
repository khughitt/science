from __future__ import annotations

from pathlib import Path

import click
import yaml


@click.group("labnote")
def labnote_group() -> None:
    """Export Labnote app packages."""


@labnote_group.command("export")
@click.option(
    "--project-root",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True, exists=True),
    default=Path("."),
    show_default=True,
    help="Science project root containing science.yaml.",
)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    required=True,
    help="Output Labnote app package directory.",
)
def labnote_export(project_root: Path, out_dir: Path) -> None:
    """Export a public Labnote app package from a Science project."""
    from science_tool.labnote_export import export_labnote_package

    try:
        diagnostics = export_labnote_package(project_root=project_root, out_dir=out_dir)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc
    warning_count = len(diagnostics.get("warnings", []))
    click.echo(f"Exported Labnote package to {out_dir} ({warning_count} warning(s))")
