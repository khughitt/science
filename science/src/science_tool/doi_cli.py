from __future__ import annotations

import click

from science_tool.doi import lookup_doi_metadata
from science_tool.output import OUTPUT_FORMATS, emit_query_rows


@click.group("doi")
def doi_group() -> None:
    """DOI metadata commands."""


@doi_group.command("lookup")
@click.argument("doi")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def doi_lookup(doi: str, output_format: str) -> None:
    """Lookup DOI metadata via Crossref."""

    metadata = lookup_doi_metadata(doi)
    rows = [{"field": key, "value": str(value)} for key, value in metadata.items()]
    emit_query_rows(
        output_format=output_format,
        title="DOI Lookup",
        columns=[("field", "Field"), ("value", "Value")],
        rows=rows,
    )
