from __future__ import annotations

from datetime import datetime
from typing import cast

import click

from science_tool.output import OUTPUT_FORMATS, emit_query_rows


@click.group("telemetry")
def telemetry_group() -> None:
    """Local telemetry reporting commands."""


@telemetry_group.command("status")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
def telemetry_status_cmd(output_format: str) -> None:
    """Show local telemetry status."""
    from science_tool.telemetry import get_telemetry_dir, read_events, telemetry_enabled

    telemetry_dir = get_telemetry_dir()
    rows = [
        {
            "enabled": telemetry_enabled(),
            "telemetry_dir": str(telemetry_dir),
            "event_count": len(read_events(telemetry_dir)),
        }
    ]
    emit_query_rows(
        output_format=output_format,
        title="Telemetry Status",
        columns=[
            ("enabled", "Enabled"),
            ("telemetry_dir", "Directory"),
            ("event_count", "Events"),
        ],
        rows=rows,
    )


@telemetry_group.command("report")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
@click.option("--errors", "include_errors", is_flag=True, help="Include recent command failures.")
@click.option("--limit", default=5, type=click.IntRange(1, 100), show_default=True, help="Recent error rows to show.")
def telemetry_report_cmd(output_format: str, include_errors: bool, limit: int) -> None:
    """Summarize local telemetry events."""
    from science_tool.telemetry import get_telemetry_dir, read_events, recent_error_rows, summarize_events

    events = read_events(get_telemetry_dir())
    summary = summarize_events(events)
    if include_errors:
        summary["recent_errors"] = recent_error_rows(events, limit=limit)
    rows = [summary]
    emit_query_rows(
        output_format=output_format,
        title="Telemetry Report",
        columns=[
            ("total_events", "Events"),
            ("event_types", "Event types"),
            ("commands", "Commands"),
            ("error_classes", "Errors"),
            ("exit_codes", "Exit codes"),
        ],
        rows=rows,
    )
    if include_errors and output_format != "json":
        emit_query_rows(
            output_format=output_format,
            title="Recent Errors",
            columns=[
                ("timestamp", "Timestamp", {"no_wrap": True}),
                ("failure", "Failure"),
                ("argv", "Argv"),
            ],
            rows=_telemetry_error_table_rows(cast(list[dict[str, object]], summary["recent_errors"])),
        )


@telemetry_group.command("export")
@click.option("--format", "output_format", default="jsonl", type=click.Choice(["jsonl"]))
def telemetry_export_cmd(output_format: str) -> None:
    """Export local telemetry events."""
    from science_tool.telemetry import export_events_jsonl, get_telemetry_dir, read_events

    if output_format == "jsonl":
        click.echo(export_events_jsonl(read_events(get_telemetry_dir())), nl=False)


@telemetry_group.command("prune")
@click.option("--before", "before_date", required=True, type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
def telemetry_prune_cmd(before_date: datetime, output_format: str) -> None:
    """Remove local telemetry events before a date."""
    from science_tool.telemetry import get_telemetry_dir, prune_events

    telemetry_dir = get_telemetry_dir()
    cutoff = before_date.date()
    removed = prune_events(telemetry_dir, before=cutoff)
    rows = [{"before": cutoff.isoformat(), "removed": removed, "telemetry_dir": str(telemetry_dir)}]
    emit_query_rows(
        output_format=output_format,
        title="Telemetry Prune",
        columns=[
            ("before", "Before"),
            ("removed", "Removed"),
            ("telemetry_dir", "Directory"),
        ],
        rows=rows,
    )


def _telemetry_error_table_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    table_rows: list[dict[str, object]] = []
    for row in rows:
        failure = str(row.get("command") or "")
        details = [
            f"exit={row['exit_code']}" if isinstance(row.get("exit_code"), int) else "",
            str(row.get("error_class") or ""),
        ]
        detail_text = " ".join(detail for detail in details if detail)
        if detail_text:
            failure = f"{failure} ({detail_text})" if failure else detail_text
        table_rows.append(
            {
                "timestamp": row.get("timestamp", ""),
                "failure": failure,
                "argv": row.get("argv", ""),
            }
        )
    return table_rows
