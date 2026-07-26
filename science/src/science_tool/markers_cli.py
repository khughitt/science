"""Click CLI group for `science markers`."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import click

from science_tool.markers import scan_markers
from science_tool.markers_lifted import filter_lifted
from science_tool.output import emit


@click.group("markers")
def markers_group() -> None:
    """Annotation-token tooling for Science projects."""


@markers_group.command("scan")
@click.option(
    "--root",
    "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(("table", "json")),
    default="table",
    show_default=True,
)
@click.option(
    "--strict",
    is_flag=True,
    help="Promote INFO-severity tokens (SPECULATION, INACCESSIBLE) to WARN.",
)
@click.option(
    "--include-documentation",
    is_flag=True,
    help="Include backticked / fenced-code occurrences (audit / migration).",
)
@click.option(
    "--ignore-lifted",
    is_flag=True,
    help="Skip hits already represented in a sibling .anno.trig sidecar.",
)
def scan(
    root_path: Path,
    output_format: str,
    strict: bool,
    include_documentation: bool,
    ignore_lifted: bool,
) -> None:
    """Scan project markdown for annotation tokens."""
    root = root_path.resolve()
    hits = scan_markers(root, strict=strict, include_documentation=include_documentation)
    if ignore_lifted:
        hits = filter_lifted(hits)
    counts = Counter(h.token for h in hits)

    payload = {
        "counts": dict(counts),
        "hits": [
            {
                "file": str(h.file.relative_to(root)),
                "line": h.line,
                "token": h.token,
                "severity": h.severity,
                "in_documentation": h.in_documentation,
            }
            for h in hits
        ],
    }

    def _render() -> None:
        if not hits:
            click.echo("markers scan: no annotation tokens found")
            return

        click.echo("Counts by token:")
        for token, count in sorted(counts.items()):
            click.echo(f"  {token}: {count}")
        click.echo()
        for h in hits:
            rel = h.file.relative_to(root)
            click.echo(f"  {rel}:{h.line}  [{h.token}]  {h.severity}")

    emit(output_format=output_format, payload=payload, render_text=_render)
