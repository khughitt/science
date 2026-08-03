"""`science findings` -- the trusted side of the audit write boundary.

`ingest` is a separate explicit command. `science health` stays read-only: a
diagnostic run never writes cases as a side effect.
"""

from __future__ import annotations

from io import StringIO
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Sequence, cast

import click
import yaml
from pydantic import ValidationError
from science_model.audit import CASE_STATUSES
from science_model.frontmatter import atomic_write_text
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from science_tool.data_root import project_config_path
from science_tool.findings.ingest import ingestion_authority
from science_tool.instruments import InstrumentStatus
from science_tool.output import OUTPUT_FORMATS, emit

if TYPE_CHECKING:
    from science_tool.findings.acceptance_migration import AcceptanceMigration
    from science_tool.validate.acceptance import AcceptedValidationEntry


@click.group("findings")
def findings_group() -> None:
    """Ingest and inspect audit findings."""


def run_acceptance_migration(project_root: Path) -> AcceptanceMigration:
    """Classify every configured validation acceptance against one health run."""
    from science_tool.findings.acceptance_migration import MigrationRow, classify_migration
    from science_tool.findings.producers import validate_finding
    from science_tool.graph.health_checks.validate import execute_validation
    from science_tool.validate.acceptance import (
        LegacyAcceptance,
        accepted_validation_entries,
        classify_acceptance_entry,
    )

    entries = accepted_validation_entries(project_root)
    classified = [classify_acceptance_entry(entry) for entry in entries]
    if not any(isinstance(entry, LegacyAcceptance) for entry in classified):
        return classify_migration(entries, (), {})

    execution = execute_validation(project_root)
    producer_statuses: dict[str, InstrumentStatus] = {
        producer_id: cast(InstrumentStatus, result.instrument.status)
        for producer_id, result in execution.run_result.producer_results.items()
    }
    rows = [
        MigrationRow(
            finding=finding,
            finding_id=validate_finding(execution.run_result.registry, "validate", finding),
        )
        for finding in execution.producer_result.instrument.rows
    ]
    return classify_migration(entries, rows, producer_statuses)


def render_migrated_config(
    original_text: str,
    entries: Sequence[AcceptedValidationEntry],
) -> str:
    """Replace only ``health.accepted_validation`` while preserving YAML presentation."""
    yaml_round_trip = YAML(typ="rt")
    yaml_round_trip.preserve_quotes = True
    yaml_round_trip.indent(mapping=2, sequence=4, offset=2)
    yaml_round_trip.width = 4096
    document = yaml_round_trip.load(original_text)
    if not isinstance(document, dict):
        raise ValueError("science.yaml must be a mapping")
    health = document.get("health")
    if not isinstance(health, dict):
        raise ValueError("science.yaml health must be a mapping")
    if not isinstance(health.get("accepted_validation"), list):
        raise ValueError("science.yaml health.accepted_validation must be a list")
    health["accepted_validation"] = [entry.model_dump(mode="json", exclude_none=True) for entry in entries]
    stream = StringIO()
    yaml_round_trip.dump(document, stream)
    return stream.getvalue()


def apply_migrated_config(
    project_root: Path,
    *,
    expected_original: str,
    rendered: str,
) -> None:
    path = project_config_path(project_root)
    if path.read_text(encoding="utf-8") != expected_original:
        raise ValueError("science.yaml changed after migration classification")
    atomic_write_text(path, rendered)


def _read_required_acceptance_config(project_root: Path) -> str:
    original = project_config_path(project_root).read_text(encoding="utf-8")
    document = yaml.safe_load(original)
    if not isinstance(document, dict):
        raise ValueError("science.yaml must be a mapping")
    if "health" not in document:
        return original
    health = document["health"]
    if not isinstance(health, dict):
        raise ValueError("science.yaml health must be a mapping")
    if "accepted_validation" not in health:
        return original
    if not isinstance(health["accepted_validation"], list):
        raise ValueError("science.yaml health.accepted_validation must be a list")
    return original


def _migration_payload(migration: AcceptanceMigration, *, applied: bool) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for entry in migration.entries:
        row: dict[str, object] = {
            "entry_index": entry.entry_index,
            "verdict": entry.verdict,
            "detail": entry.detail,
        }
        if entry.replacement is not None:
            row["finding_id"] = entry.replacement.finding_id
            row["severity_scope"] = list(entry.replacement.severity_scope)
        entries.append(row)
    return {
        "applied": applied,
        "can_apply": migration.can_apply,
        "needs_write": migration.needs_write,
        "indeterminate_producers": list(migration.indeterminate_producers),
        "entries": entries,
    }


@findings_group.command("migrate-acceptances")
@click.option(
    "--project-root",
    type=click.Path(path_type=Path, file_okay=False),
    default=Path("."),
    show_default=True,
)
@click.option("--apply", is_flag=True, help="Atomically rewrite science.yaml.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
def migrate_acceptances_command(
    project_root: Path,
    apply: bool,
    output_format: str,
) -> None:
    """Classify legacy validation acceptances and optionally replace them atomically."""
    try:
        original = _read_required_acceptance_config(project_root)
        migration = run_acceptance_migration(project_root)
        applied = False
        if apply and migration.can_apply and migration.needs_write:
            rendered = render_migrated_config(original, migration.output_entries)
            apply_migrated_config(
                project_root,
                expected_original=original,
                rendered=rendered,
            )
            applied = True
    except (OSError, ValidationError, ValueError, yaml.YAMLError, YAMLError) as exc:
        message = f"refused: {exc}"
        emit(
            output_format=output_format,
            payload={
                "applied": False,
                "can_apply": False,
                "needs_write": False,
                "indeterminate_producers": [],
                "entries": [],
                "error": message,
            },
            render_text=lambda: click.echo(message),
        )
        raise click.exceptions.Exit(2) from exc

    payload = _migration_payload(migration, applied=applied)

    def render_text() -> None:
        for entry in migration.entries:
            click.echo(f"{entry.entry_index}: {entry.verdict}: {entry.detail}")

    emit(output_format=output_format, payload=payload, render_text=render_text)
    if not migration.can_apply:
        raise click.exceptions.Exit(2)


@findings_group.command("ingest")
@click.argument("report_path", type=click.Path(path_type=Path, exists=True))
@click.option("--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
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
        registry, context = ingestion_authority(project_root)
        outcome = ingest_report(
            project_root,
            report,
            registry,
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
@click.option("--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True)
@click.option(
    "--status",
    type=click.Choice(CASE_STATUSES),
    default=None,
    help="Filter to one lifecycle status.",
)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
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
