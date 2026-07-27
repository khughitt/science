"""`science findings` -- the trusted side of the audit write boundary.

`ingest` is a separate explicit command. `science health` stays read-only: a
diagnostic run never writes cases as a side effect.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from science_model.audit import CASE_STATUSES

from science_tool.output import OUTPUT_FORMATS, emit


@click.group("findings")
def findings_group() -> None:
    """Ingest and inspect audit findings."""


def _registry():
    """The derived registry. Plan 2 populates it from real producers."""
    from science_tool.findings.producers import build_registry

    return build_registry([])


@findings_group.command("ingest")
@click.argument("report_path", type=click.Path(path_type=Path, exists=True))
@click.option(
    "--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True
)
@click.option(
    "--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True
)
def ingest_command(report_path: Path, project_root: Path, output_format: str) -> None:
    """Validate a report and upsert its findings into `doc/audits/cases/`."""
    from science_tool.findings.ingest import IngestError, ingest_report, load_report

    try:
        report = load_report(project_root, report_path)
        outcome = ingest_report(project_root, report, _registry())
    except IngestError as exc:
        message = f"refused: {exc}"
        emit(
            output_format=output_format,
            payload={"ingested": False, "error": message},
            render_text=lambda: click.echo(message),
        )
        sys.exit(2)

    emit(
        output_format=output_format,
        payload=outcome.model_dump(mode="json"),
        render_text=lambda: click.echo(
            f"{outcome.records_written} new case(s), "
            f"{outcome.occurrences_appended} occurrence(s) appended, "
            f"{outcome.occurrences_skipped} skipped as already recorded"
        ),
    )


@findings_group.command("list")
@click.option(
    "--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True
)
@click.option(
    "--status",
    type=click.Choice(CASE_STATUSES),
    default=None,
    help="Filter to one lifecycle status.",
)
@click.option(
    "--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True
)
def list_command(project_root: Path, status: str | None, output_format: str) -> None:
    """List stored cases. Read-only."""
    from science_tool.findings.storage import CaseStorageError, load_cases

    try:
        records = load_cases(project_root)
    except CaseStorageError as exc:
        raise click.UsageError(f"could not load cases: {exc}") from exc

    if status is not None:
        records = [record for record in records if record.status == status]

    payload = [
        {
            "finding_id": record.finding_id,
            "rule_id": record.rule_id,
            "status": record.status,
            "occurrences": len(record.occurrences),
            "confirmations": record.confirmation_count(),
        }
        for record in records
    ]

    def render_text() -> None:
        for row in payload:
            click.echo(
                f"{row['status']:<10} {row['rule_id']:<40} "
                f"{row['occurrences']}occ {row['confirmations']}conf "
                f"{row['finding_id'][:12]}"
            )

    emit(output_format=output_format, payload=payload, render_text=render_text)
