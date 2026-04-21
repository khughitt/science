from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import click
from rich.console import Console
from rich.table import Table

OUTPUT_FORMATS: tuple[str, str] = ("table", "json")


def emit_query_rows(
    *,
    output_format: str,
    title: str,
    columns: list[tuple[str, str]],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    if output_format == "json":
        click.echo(json.dumps({"format": "json", "rows": rows}, indent=2))
        return

    table = Table(title=title)
    for _, label in columns:
        table.add_column(label)

    for row in rows:
        table.add_row(*(str(row.get(key, "")) for key, _ in columns))

    console = Console(file=click.get_text_stream("stdout"), force_terminal=False, color_system=None)
    console.print(table)
