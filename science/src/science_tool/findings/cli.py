"""`science findings` -- the trusted side of the audit write boundary.

`ingest` is a separate explicit command. `science health` stays read-only: a
diagnostic run never writes cases as a side effect.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
import yaml
from science_model.audit import CASE_STATUSES

from science_tool.graph.entity_registry import EntityRegistry
from science_tool.output import OUTPUT_FORMATS, emit


@click.group("findings")
def findings_group() -> None:
    """Ingest and inspect audit findings."""


def _registry(entity_registry: EntityRegistry):
    """The derived registry. Plan 2 populates it from real producers."""
    from science_tool.findings.catalog import build_registry_for_entity_registry

    return build_registry_for_entity_registry(entity_registry)


def _load_ingestion_context(project_root: Path):
    """Build the trusted entity universe through the graph's strict source boundary."""
    from science_tool.findings.ingest import IngestionContext
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(project_root)
    context = IngestionContext(
        canonical_entity_ids=frozenset(
            entity.canonical_id for entity in sources.entities
        )
    )
    return context, sources.registry


@findings_group.command("ingest")
@click.argument("report_path", type=click.Path(path_type=Path, exists=True))
@click.option(
    "--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True
)
@click.option(
    "--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True
)
@click.option(
    "--attest-ingestion-ref",
    required=True,
    help="Trusted ingestion reference that the report must match exactly.",
)
@click.option(
    "--attest-generated-at",
    required=True,
    help="Trusted generation timestamp that the report must match exactly.",
)
@click.option(
    "--attest-producer-id",
    "attest_producer_ids",
    multiple=True,
    required=True,
    help="Trusted producer ID; repeat for the exact producer set.",
)
def ingest_command(
    report_path: Path,
    project_root: Path,
    output_format: str,
    attest_ingestion_ref: str,
    attest_generated_at: str,
    attest_producer_ids: tuple[str, ...],
) -> None:
    """Validate a report and upsert its findings into `doc/audits/cases/`."""
    from science_tool.findings.ingest import (
        IngestionProvenance,
        ingest_report,
        load_report,
    )
    from science_tool.commons.errors import CommonsError

    try:
        report = load_report(project_root, report_path)
        provenance = IngestionProvenance(
            ingestion_ref=attest_ingestion_ref,
            generated_at=attest_generated_at,
            producer_ids=frozenset(attest_producer_ids),
        )
        context, entity_registry = _load_ingestion_context(project_root)
        outcome = ingest_report(
            project_root,
            report,
            _registry(entity_registry),
            provenance=provenance,
            context=context,
        )
    except (CommonsError, OSError, ValueError, yaml.YAMLError) as exc:
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
