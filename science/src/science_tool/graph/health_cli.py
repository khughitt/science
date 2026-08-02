"""``science health`` command over the shared AuditReport v2 contract."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Protocol
from uuid import uuid4

import click
from rich.console import Console
from science_model.audit import (
    AuditReport,
    EntitySubject,
    FindingSubject,
    IdentifierSubject,
    PathSubject,
)

from science_tool.findings.producers import FindingRegistry
from science_tool.findings.reporting import report_sort_key
from science_tool.graph.health_projection import ProjectedHealthReport
from science_tool.output import emit, serialize_json
from science_tool.validate.acceptance import (
    ACCEPTANCE_CONFIGURATION_RULES,
)


def report_has_invalid_acceptance_configuration(
    report: AuditReport,
) -> bool:
    return any(item.finding.rule_id in ACCEPTANCE_CONFIGURATION_RULES for item in report.findings)


class HealthSink(Protocol):
    @property
    def console(self) -> Console: ...

    def echo(self, text: str = "") -> None: ...


def _subject_text(subject: FindingSubject) -> str:
    if isinstance(subject, EntitySubject):
        return subject.ref
    if isinstance(subject, PathSubject):
        pointer = f"#{subject.pointer}" if subject.pointer else ""
        return f"{subject.path}{pointer}"
    if isinstance(subject, IdentifierSubject):
        return f"{subject.namespace}:{subject.value}"
    return "project"


def render_health_report(
    display: ProjectedHealthReport,
    registry: FindingRegistry,
    sink: HealthSink,
) -> None:
    """Render findings generically; metrics never become synthetic findings."""
    from rich.table import Table

    report = display.report
    if report.meta.timings:
        sink.echo("Health timings:")
        for row in report.meta.timings:
            name = row.get("name")
            duration = row.get("duration_seconds")
            if not isinstance(name, str) or not isinstance(duration, int | float):
                raise TypeError("health timing rows require string name and numeric duration")
            sink.echo(f"  {name}: {duration:.3f}s")
        sink.echo(f"  total: {report.meta.total_duration_seconds:.3f}s")

    for caveat in report.caveats:
        detail = caveat.reason or caveat.code or ""
        sink.echo(f"Note [{caveat.producer_id}]: {detail}")

    if report.unwired:
        table = Table(title=f"Diagnostics that could not run ({len(report.unwired)})")
        table.add_column("Producer")
        table.add_column("Code")
        table.add_column("Reason")
        for item in report.unwired:
            table.add_row(item.producer_id, item.code, item.reason or "")
        sink.console.print(table)

    grouped: dict[str, list] = defaultdict(list)
    for item in display.findings:
        grouped[registry.rule(item.finding.rule_id).section].append(item)
    for section_id in sorted(
        grouped,
        key=lambda value: registry.section(value).section_order,
    ):
        section = registry.section(section_id)
        rows = sorted(
            grouped[section_id],
            key=lambda item: report_sort_key(registry, item.finding),
        )
        table = Table(title=f"{section.title} ({len(rows)})")
        table.add_column("Severity")
        table.add_column("Subject")
        table.add_column("Rule")
        table.add_column("Message")
        for item in rows:
            finding = item.finding
            table.add_row(
                finding.severity,
                _subject_text(finding.subject),
                finding.rule_id,
                finding.message,
            )
        sink.console.print(table)

    if report.accepted:
        sink.echo(f"Accepted findings: {len(report.accepted)}")
    for producer_id, metrics in report.metrics.items():
        sink.echo(
            f"Metrics [{producer_id}]: {serialize_json(metrics.model_dump(mode='json'), indent=None, sort_keys=True)}"
        )

    sink.echo(f"Findings displayed: {len(display.findings)} of {report.totals.findings_total} total.")
    if report.totals.findings_total == 0 and not report.unwired:
        sink.echo("Project is clean.")
    elif report.unwired:
        sink.echo("Project is not clean: one or more diagnostics could not run.")


@click.command("health")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option(
    "--format",
    "output_format",
    default="table",
    show_default=True,
    type=click.Choice(["table", "json"]),
)
@click.option("--timings", is_flag=True, help="Include per-check timing diagnostics.")
@click.option("--fast", is_flag=True, help="Run checks that do not require project sources.")
@click.option("--check", "checks", multiple=True, help="Run only this named health check.")
@click.option("--skip", "skip_checks", multiple=True, help="Skip this named health check.")
@click.option("--list-checks", is_flag=True, help="List available health checks and exit.")
@click.option(
    "--severity",
    type=click.Choice(["error", "warn", "all"]),
    default="warn",
    show_default=True,
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
)
@click.option(
    "--ingestion-ref", default=None,
    help="Supervisor-dictated ingestion reference. Requires --generated-at.",
)
@click.option(
    "--generated-at", default=None,
    help="Supervisor-dictated ISO-8601 generation instant. Requires --ingestion-ref.",
)
def health_command(
    project_root: Path,
    output_format: str,
    timings: bool,
    fast: bool,
    checks: tuple[str, ...],
    skip_checks: tuple[str, ...],
    list_checks: bool,
    severity: str,
    output_path: Path | None,
    ingestion_ref: str | None,
    generated_at: str | None,
) -> None:
    from rich.table import Table

    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.graph.health import execute_health_report, list_health_checks
    from science_tool.graph.health_projection import (
        ProjectedHealthReport,
        project_health_report,
    )

    sink = BoundedSink(
        lookup("health"),
        output_path=output_path,
        command_path="health",
        complete_via=build_complete_via(
            click.get_current_context(),
            output_hint=hint_for("health", output_format),
        ),
    )
    project_root = project_root.resolve()
    if list_checks:
        available = list_health_checks()

        def render_checks() -> None:
            table = Table(title="Health checks")
            table.add_column("Check")
            table.add_column("Requires sources")
            table.add_column("Description")
            for row in available:
                table.add_row(
                    str(row["name"]),
                    "yes" if row["requires_sources"] else "no",
                    str(row["description"]),
                )
            sink.console.print(table)

        emit(
            output_format=output_format,
            payload={"checks": available},
            render_text=render_checks,
            sink=sink,
        )
        sink.flush()
        return

    if (ingestion_ref is None) != (generated_at is None):
        raise click.UsageError(
            "--ingestion-ref and --generated-at must be supplied together: a dictated "
            "reference with an invented timestamp is not an attestable provenance"
        )
    if ingestion_ref is None:
        ingestion_ref = f"health:{uuid4().hex}"
        generated_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    assert generated_at is not None
    try:
        execution = execute_health_report(
            project_root,
            ingestion_ref=ingestion_ref,
            generated_at=generated_at,
            collect_timings=timings,
            checks=frozenset(checks) or None,
            skip_checks=frozenset(skip_checks) or None,
            fast=fast,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    report = execution.report
    registry = execution.registry
    displayed = (
        ProjectedHealthReport(report=report, findings=report.findings)
        if output_path is not None
        else project_health_report(
            report,
            registry=registry,
            threshold=severity,
        )
    )
    emit(
        output_format=output_format,
        payload=report.model_dump(mode="json"),
        render_text=lambda: render_health_report(displayed, registry, sink),
        indent=2 if output_path is not None else None,
        separators=None if output_path is not None else (",", ":"),
        sink=sink,
    )
    sink.flush()
    if output_path is not None:
        click.echo(bounded_control_notice(f"wrote the complete health report to {output_path}"))
    if report_has_invalid_acceptance_configuration(report):
        sys.exit(2)
