from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import click
from rich.table import Table

from science_tool.styles import get_console

OUTPUT_FORMATS: tuple[str, str] = ("table", "json")


def emit(
    *,
    output_format: str,
    payload: Any,
    render_text: Callable[[], None],
    indent: int | None = 2,
    sort_keys: bool = False,
    ensure_ascii: bool = True,
    default: Callable[[Any], Any] | None = None,
) -> None:
    """Emit ``payload`` as JSON on stdout when ``output_format == "json"``, else
    invoke ``render_text`` for human output.

    Serialization kwargs mirror ``json.dumps`` so existing call sites keep their
    exact byte output. Diagnostics must never reach stdout through this function:
    the JSON branch writes only ``json.dumps(payload, ...)``.
    """
    if output_format == "json":
        click.echo(json.dumps(payload, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii, default=default))
        return
    render_text()


def emit_query_rows(
    *,
    output_format: str,
    title: str,
    columns: Sequence[tuple[str, str] | tuple[str, str, dict[str, Any]]],
    rows: Sequence[Mapping[str, Any]],
    meta: Mapping[str, Any] | None = None,
    renderers: Mapping[str, Callable[[Any, Mapping[str, Any]], Any]] | None = None,
) -> None:
    rows_list = list(rows)
    payload: dict[str, Any] = {"format": "json", "rows": rows_list}
    if meta is not None:
        payload["meta"] = dict(meta)

    def _render() -> None:
        table = Table(title=title)
        for col in columns:
            _, label, *rest = col
            col_kwargs: dict[str, Any] = rest[0] if rest else {}
            table.add_column(label, **col_kwargs)

        cell_renderers = renderers or {}
        for row in rows_list:
            cells: list[Any] = []
            for key, *_ in columns:
                value = row.get(key, "")
                renderer = cell_renderers.get(key)
                cells.append(renderer(value, row) if renderer is not None else str(value))
            table.add_row(*cells)

        console = get_console(file=click.get_text_stream("stdout"))
        console.print(table)

    emit(output_format=output_format, payload=payload, render_text=_render)
