from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeVar

import click
from rich.table import Table

from science_tool.budget.projection import project_rows
from science_tool.budget.sink import BoundedSink
from science_tool.instruments import InstrumentResult, ValidationVerdict
from science_tool.styles import get_console

OUTPUT_FORMATS: tuple[str, str] = ("table", "json")

RowT = TypeVar("RowT")

# `science_tool.entities._validate_prospective_write(s)` prefixes any baseline-corpus
# audit failure it surfaces as a warning with this string, to distinguish it from a
# warning about the write itself.
PREEXISTING_AUDIT_PREFIX = "pre-existing audit failure:"


def serialize_json(
    payload: Any,
    *,
    indent: int | None = 2,
    sort_keys: bool = False,
    ensure_ascii: bool = True,
    default: Callable[[Any], Any] | None = None,
    separators: tuple[str, str] | None = None,
) -> str:
    """Serialize an output payload through the canonical JSON authority."""
    return json.dumps(
        payload,
        indent=indent,
        sort_keys=sort_keys,
        ensure_ascii=ensure_ascii,
        default=default,
        separators=separators,
    )


def summarize_preexisting_warnings(warnings: Sequence[str], *, show_preexisting: bool) -> tuple[list[str], str | None]:
    """Split WARNINGS into what a write command should print, plus an optional note.

    `_validate_prospective_write(s)` warnings mix two things a write command must not
    treat alike: the write's OWN new findings, and pre-existing whole-corpus audit
    failures it happens to surface as a side effect. The latter can grow with total
    project size, so printing them in full would turn an O(1) write confirmation into
    an O(project) one (fb-2026-06-28-015, generalized past `dataset verify-access` to
    every write command that surfaces these warnings).

    Returns `(to_print, note)`. `to_print` always keeps the write's own warnings, in
    their original order. When `show_preexisting` (or there are none to collapse), the
    pre-existing ones are included too and `note` is `None`. Otherwise the pre-existing
    warnings are dropped from `to_print` and `note` names how many were omitted and how
    to see them -- never truncated, always a path back to the full set.
    """
    if show_preexisting:
        return list(warnings), None
    preexisting_count = sum(1 for warning in warnings if warning.startswith(PREEXISTING_AUDIT_PREFIX))
    if not preexisting_count:
        return list(warnings), None
    kept = [warning for warning in warnings if not warning.startswith(PREEXISTING_AUDIT_PREFIX)]
    note = (
        f"note: {preexisting_count} pre-existing project audit warning(s) unrelated to this "
        "write (run `science validate`, or --show-preexisting to list here)"
    )
    return kept, note


def emit(
    *,
    output_format: str,
    payload: Any,
    render_text: Callable[[], None],
    indent: int | None = 2,
    sort_keys: bool = False,
    ensure_ascii: bool = True,
    default: Callable[[Any], Any] | None = None,
    separators: tuple[str, str] | None = None,
    sink: BoundedSink | None = None,
) -> None:
    """Emit ``payload`` as JSON when ``output_format == "json"``, else ``render_text()``.

    Serialization kwargs mirror ``json.dumps`` so existing call sites keep their exact
    byte output. Diagnostics must never reach stdout through this function: the JSON
    branch writes only ``json.dumps(payload, ...)``, so truncation is recorded INSIDE
    ``payload`` by projection, never echoed alongside it.

    CONTRACT: when ``sink`` is supplied, ``render_text`` must write only into that sink
    (``sink.console`` / ``sink.echo``). ``emit`` cannot enforce this for a caller-supplied
    callback -- ``tests/test_budget_boundary.py`` checks it per command.

    When ``sink`` is None the historical unbudgeted behaviour is preserved exactly.
    """
    if output_format == "json":
        rendered = serialize_json(
            payload,
            indent=indent,
            sort_keys=sort_keys,
            ensure_ascii=ensure_ascii,
            default=default,
            separators=separators,
        )
        if sink is None:
            click.echo(rendered)
        else:
            sink.echo(rendered)
        return
    render_text()


def unwrap_instrument(result: InstrumentResult[RowT], *, what: str) -> list[RowT]:
    """Take the rows of an instrument result, REFUSING to render an unwired one.

    This is the one place the CLI turns an ``InstrumentResult`` back into rows, and it
    exists so that ``unwired`` cannot quietly become "no results found". An unwired
    instrument did not run; its rows are meaningless, and printing them as an empty
    table would be the exact failure the type was introduced to stop -- so it raises.

    A ``reason`` on a SUCCESSFUL run is a caveat (part of the input was dropped) and
    goes to stderr, leaving stdout a clean, parseable payload.
    """
    if result.status == "unwired":
        raise click.ClickException(f"{what} did not run ({result.code}): {result.reason}")
    if result.reason:
        click.echo(f"notice ({result.code}): {result.reason}", err=True)
    return result.rows


def unwrap_verdict(verdict: ValidationVerdict[RowT], *, what: str) -> tuple[list[RowT], bool]:
    """Turn a ValidationVerdict into ``(rows, has_failures)``, REFUSING to render unwired.

    The parallel of ``unwrap_instrument`` for the verdict axis: an unwired validator did
    not run, so emitting its empty rows as a clean report would be the exact silent-run lie
    the convergence exists to stop -- so it raises before anything is rendered.
    """
    if verdict.status == "unwired":
        raise click.ClickException(f"{what} could not run ({verdict.code}): {verdict.reason}")
    if verdict.reason:
        click.echo(f"notice ({verdict.code}): {verdict.reason}", err=True)
    return verdict.rows, verdict.status == "failed"


def emit_query_rows(
    *,
    output_format: str,
    title: str,
    columns: Sequence[tuple[str, str] | tuple[str, str, dict[str, Any]]],
    rows: Sequence[Mapping[str, Any]],
    meta: Mapping[str, Any] | None = None,
    renderers: Mapping[str, Callable[[Any, Mapping[str, Any]], Any]] | None = None,
    sink: BoundedSink | None = None,
) -> None:
    projected = project_rows(rows, sink.max_rows if sink is not None else None)
    rows_list = projected.rows

    payload: dict[str, Any] = {"format": "json", "rows": rows_list}
    if meta is not None:
        meta_out = dict(meta)
        # This function owns the projection, so it owns the row count. `returned_count`
        # means "rows in THIS payload"; a caller computing it before projection would
        # report 366 next to 40 rows. Reconciling here is the only way the two cannot
        # disagree.
        if "returned_count" in meta_out:
            meta_out["returned_count"] = len(rows_list)
        payload["meta"] = meta_out
    if projected.truncated:
        payload["truncation"] = {
            "omitted": projected.omitted,
            "total": projected.total,
            "complete_via": sink.complete_via if sink is not None else "",
        }

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

        if sink is None:
            get_console(file=click.get_text_stream("stdout")).print(table)
            return

        sink.console.print(table)
        if projected.truncated:
            sink.echo(f"showing {len(rows_list)} of {projected.total} rows")
            sink.echo(f"  complete output:  {sink.complete_via}")

    emit(output_format=output_format, payload=payload, render_text=_render, sink=sink)
