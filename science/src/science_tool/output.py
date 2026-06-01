from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import click
from rich.table import Table

from science_tool.styles import get_console

OUTPUT_FORMATS: tuple[str, str] = ("table", "json")


def emit_query_rows(
    *,
    output_format: str,
    title: str,
    columns: list[tuple[str, str]],
    rows: Sequence[Mapping[str, Any]],
    meta: Mapping[str, Any] | None = None,
    renderers: Mapping[str, Callable[[Any, Mapping[str, Any]], Any]] | None = None,
) -> None:
    if output_format == "json":
        payload: dict[str, Any] = {"format": "json", "rows": list(rows)}
        if meta is not None:
            payload["meta"] = dict(meta)
        click.echo(json.dumps(payload, indent=2))
        return

    table = Table(title=title)
    for _, label in columns:
        table.add_column(label)

    cell_renderers = renderers or {}
    for row in rows:
        cells: list[Any] = []
        for key, _ in columns:
            value = row.get(key, "")
            renderer = cell_renderers.get(key)
            cells.append(renderer(value, row) if renderer is not None else str(value))
        table.add_row(*cells)

    console = get_console(file=click.get_text_stream("stdout"))
    console.print(table)
