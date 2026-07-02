from __future__ import annotations

import json
from pathlib import Path

import click


@click.command("search")
@click.argument("query")
@click.option(
    "--archived",
    is_flag=True,
    default=False,
    help="Search the archive index (required; live search not yet implemented).",
)
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--format", "output_format", type=click.Choice(["json", "text"]), default="json", show_default=True)
def search_command(query: str, archived: bool, project_root: Path, output_format: str) -> None:
    """Search entities. P3 supports --archived only (reads the archive index)."""
    if not archived:
        raise click.UsageError(
            "science search currently supports only --archived (live entity search is not implemented)."
        )
    from science_tool.archive import search_archive

    hits = search_archive(project_root, query)
    if output_format == "json":
        click.echo(json.dumps(hits, indent=2, sort_keys=True))
    else:
        for h in hits:
            click.echo(f"{h['id']}  [{h['kind']}]  {h['title'] or ''}")
