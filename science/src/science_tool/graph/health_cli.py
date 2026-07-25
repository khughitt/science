"""`science health` command — aggregate project diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import click

from science_tool.output import emit


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
@click.option(
    "--timings",
    is_flag=True,
    help="Include per-check timing diagnostics.",
)
@click.option(
    "--fast",
    is_flag=True,
    help="Run only health checks that do not require loading project sources.",
)
@click.option(
    "--check",
    "checks",
    multiple=True,
    help="Run only the named health check. May be passed multiple times.",
)
@click.option(
    "--skip",
    "skip_checks",
    multiple=True,
    help="Skip the named health check. May be passed multiple times.",
)
@click.option(
    "--list-checks",
    is_flag=True,
    help="List available health checks and exit.",
)
@click.option(
    "--severity",
    type=click.Choice(["error", "warn", "all"]),
    default="warn",
    show_default=True,
    help="Minimum severity to display. A THRESHOLD, not an equality filter: "
    "`warn` shows warnings AND errors.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted report to PATH instead of stdout.",
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
) -> None:
    """Aggregate diagnostics for the project: unresolved refs, lingering tags, etc."""
    from rich.table import Table

    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.graph.health import build_health_report, list_health_checks
    from science_tool.graph.health_checks.archive_lag import archive_lag_total

    sink = BoundedSink(
        lookup("health"),
        output_path=output_path,
        command_path="health",
        complete_via=build_complete_via(
            click.get_current_context(), output_hint="health.json"
        ),
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete health report to {output_path}")
        if output_path is not None
        else None
    )

    project_root = project_root.resolve()
    if list_checks:
        available_checks = list_health_checks()

        def _render_checks() -> None:
            table = Table(title="Health checks")
            table.add_column("Check")
            table.add_column("Requires sources")
            table.add_column("Description")
            for row in available_checks:
                table.add_row(
                    str(row["name"]),
                    "yes" if row["requires_sources"] else "no",
                    str(row["description"]),
                )
            sink.console.print(table)

        emit(
            output_format=output_format,
            payload={"checks": available_checks},
            render_text=_render_checks,
            sink=sink,
        )
        sink.flush()
        return

    try:
        if timings or fast or checks or skip_checks:
            report = build_health_report(
                project_root,
                collect_timings=timings,
                checks=frozenset(checks) or None,
                skip_checks=frozenset(skip_checks) or None,
                fast=fast,
            )
        else:
            report = build_health_report(project_root)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    from science_tool.graph.health_projection import (
        SECTION_ROW_CAP,
        project_health_report,
    )

    # --output is complete: no projection at all when writing to a file.
    displayed: dict[str, Any] = (
        cast("dict[str, Any]", report)
        if output_path is not None
        else project_health_report(cast("dict[str, Any]", report), threshold=severity)
    )

    def _render_report() -> None:
        if timings:
            meta = displayed.get("_meta") or {}
            timing_rows = meta.get("timings") or []
            total_duration = meta.get("total_duration_seconds")
            click.echo("Health timings:", err=True)
            for row in timing_rows:
                click.echo(f"  {row['name']}: {row['duration_seconds']:.3f}s", err=True)
            if isinstance(total_duration, int | float):
                click.echo(f"  total: {total_duration:.3f}s", err=True)

        layered_claims = displayed["layered_claims"]
        archive_lag = displayed["archive_lag"]
        lag_total = archive_lag_total(archive_lag)

        managed_artifacts = displayed.get("managed_artifacts") or []
        tooling_scaffold = displayed.get("tooling_scaffold") or []
        agent_context = displayed.get("agent_context") or []
        unregistered_ref_kinds = displayed.get("unregistered_ref_kinds") or []
        entity_identity = displayed.get("entity_identity") or []
        schema_invalid = displayed.get("schema_invalid") or []
        validation = displayed.get("validation") or []
        accepted_validation = displayed.get("accepted_validation") or []
        prose_epistemics = displayed.get("prose_epistemics") or {}
        raw_prose_epistemics_findings = prose_epistemics.get("findings") if isinstance(prose_epistemics, dict) else None
        prose_epistemics_findings: list[dict[str, object]] = (
            [cast("dict[str, object]", row) for row in raw_prose_epistemics_findings if isinstance(row, dict)]
            if isinstance(raw_prose_epistemics_findings, list)
            else []
        )
        cross_paper_evidence = displayed.get("cross_paper_evidence") or {}
        raw_cross_paper_findings = cross_paper_evidence.get("findings") if isinstance(cross_paper_evidence, dict) else None
        cross_paper_findings: list[dict[str, object]] = (
            [cast("dict[str, object]", row) for row in raw_cross_paper_findings if isinstance(row, dict)]
            if isinstance(raw_cross_paper_findings, list)
            else []
        )

        unwired_checks = displayed.get("unwired_checks") or []

        # An unwired check DID NOT RUN. Print it before anything else and never let a
        # report that contains one claim the project is clean: zero findings from a
        # check that never looked is not a clean bill of health.
        if unwired_checks:
            uw_table = Table(title=f"Checks that COULD NOT RUN ({len(unwired_checks)})")
            uw_table.add_column("Check", style="bold")
            uw_table.add_column("Code")
            uw_table.add_column("Why it did not run", overflow="fold")
            for row in unwired_checks:
                uw_table.add_row(row["check"], row["code"], row.get("reason") or "")
            sink.console.print(uw_table)
            sink.console.print(
                "\n[bold]These checks found nothing because they did not run — not because "
                "the project is clean.[/bold] Their input is missing; supply it, then rerun."
            )

        total_issues = report["total_issues"]
        if total_issues == 0:
            if unwired_checks:
                sink.echo(
                    f"No issues found by the checks that ran — but {len(unwired_checks)} check(s) "
                    "could not run (see above). This is NOT a clean bill of health."
                )
            else:
                sink.echo("Project is clean — no issues found.")
            if accepted_validation:
                sink.echo(f"Accepted validation warnings: {len(accepted_validation)}")
            return

        if lag_total:
            lag_table = Table(title="Tasks Archive Lag")
            lag_table.add_column("Metric", style="bold")
            lag_table.add_column("Count", justify="right")
            for key in ("done_in_active", "retired_in_active", "missing_completed"):
                lag_table.add_row(key, str(archive_lag[key]))
            sink.console.print(lag_table)
            sink.console.print(
                "\n[bold]Next:[/bold] run [cyan]science tasks archive[/cyan] to preview, then [cyan]--apply[/cyan]."
            )

        flagged_managed_artifacts = [f for f in managed_artifacts if f.get("counts_as_issue")]
        if flagged_managed_artifacts:
            ma_table = Table(title=f"Managed artifacts ({len(flagged_managed_artifacts)})")
            ma_table.add_column("Name", style="bold")
            ma_table.add_column("Status")
            ma_table.add_column("Detail")
            for row in flagged_managed_artifacts:
                ma_table.add_row(row["name"], row["status"], row["detail"])
            sink.console.print(ma_table)
            sink.console.print(
                "\n[bold]Next:[/bold] run "
                "[cyan]science project artifacts check[/cyan] / "
                "[cyan]update[/cyan] / [cyan]install[/cyan] per status."
            )

        if tooling_scaffold:
            ts_table = Table(title=f"Tooling scaffold ({len(tooling_scaffold)})")
            ts_table.add_column("Code", style="bold")
            ts_table.add_column("Detail")
            ts_table.add_column("Fix")
            for row in tooling_scaffold:
                ts_table.add_row(row["code"], row["detail"], row["fix"])
            sink.console.print(ts_table)
            sink.console.print(
                "\n[bold]Next:[/bold] follow the suggested fix for each row — "
                "see [cyan]commands/create-project.md[/cyan] for the canonical scaffold."
            )

        if agent_context:
            ac_table = Table(title=f"Agent context ({len(agent_context)})")
            ac_table.add_column("Code", style="bold")
            ac_table.add_column("File")
            ac_table.add_column("Detail")
            ac_table.add_column("Fix")
            for row in agent_context:
                ac_table.add_row(row["code"], row["source_file"], row["detail"], row["fix"])
            sink.console.print(ac_table)
            sink.console.print(
                "\n[bold]Next:[/bold] keep [cyan]CLAUDE.md[/cyan] minimal, remove [cyan]@core/*[/cyan] "
                "includes, and keep [cyan]core/overview.md[/cyan] as concise boot context."
            )

        if schema_invalid:
            si_table = Table(title=f"Schema-invalid entities ({len(schema_invalid)})")
            si_table.add_column("Kind", style="bold")
            si_table.add_column("Path")
            si_table.add_column("Detail")
            for row in schema_invalid:
                si_table.add_row(row["kind"], row["path"], row["message"])
            sink.console.print(si_table)
            sink.console.print(
                "\n[bold]Next:[/bold] fix each entity's frontmatter to satisfy its schema "
                "(these are excluded from the graph until repaired); rerun "
                "[cyan]science validate[/cyan] for the authoritative error."
            )

        if prose_epistemics_findings:
            prose_epistemics_next = "science annotate build-prose-health --write"
            pe_table = Table(title=f"Prose Epistemics ({len(prose_epistemics_findings)})")
            pe_table.add_column("Code", style="bold")
            pe_table.add_column("Source")
            pe_table.add_column("Detail")
            for row in prose_epistemics_findings:
                pe_table.add_row(
                    str(row.get("code", "")),
                    str(row.get("source_ref") or ""),
                    f"{row.get('message', '')}\nNext action: {prose_epistemics_next}",
                )
            sink.console.print(pe_table)
            sink.console.print(
                f"\n[bold]Next:[/bold] run [cyan]{prose_epistemics_next}[/cyan]."
            )

        if cross_paper_findings:
            cpe_table = Table(title=f"Cross-paper evidence ({len(cross_paper_findings)})")
            cpe_table.add_column("Reason", style="bold", no_wrap=True)
            cpe_table.add_column("Sidecar", overflow="fold")
            cpe_table.add_column("Annotation", no_wrap=True)
            cpe_table.add_column("Detail", overflow="fold")
            for row in cross_paper_findings:
                sidecar = str(row.get("sidecar", ""))
                if sidecar:
                    try:
                        sidecar = str(Path(sidecar).resolve().relative_to(project_root))
                    except ValueError:
                        pass
                reason = str(row.get("reason", ""))
                annotation = str(row.get("annotation", ""))
                detail = str(row.get("detail", ""))
                cpe_table.add_row(
                    reason,
                    sidecar,
                    annotation,
                    detail,
                )
            sink.console.print(cpe_table)
            sink.console.print(
                "\n[bold]Next:[/bold] fix stale promoted_to refs or proposition "
                "source_refs, then rerun health."
            )

        if displayed["unresolved_refs"]:
            table = Table(
                title=f"Unresolved references ({len(displayed['unresolved_refs'])})"
            )
            table.add_column("Target", style="bold")
            table.add_column("Mentions", justify="right")
            table.add_column("Suggested triage")
            table.add_column("Sources (first 3)")
            for row in displayed["unresolved_refs"]:
                srcs = ", ".join(row["sources"][:3])
                if len(row["sources"]) > 3:
                    srcs += f", … (+{len(row['sources']) - 3})"
                table.add_row(row["target"], str(row["mention_count"]), row["looks_like"], srcs)
            sink.console.print(table)

        if unregistered_ref_kinds:
            table = Table(title=f"Unregistered reference kinds ({len(unregistered_ref_kinds)})")
            table.add_column("Kind", style="bold")
            table.add_column("Field")
            table.add_column("Mentions", justify="right")
            table.add_column("Refs (first 3)")
            table.add_column("Sources (first 3)")
            for row in unregistered_ref_kinds:
                refs = ", ".join(row["refs"][:3])
                if len(row["refs"]) > 3:
                    refs += f", … (+{len(row['refs']) - 3})"
                srcs = ", ".join(row["sources"][:3])
                if len(row["sources"]) > 3:
                    srcs += f", … (+{len(row['sources']) - 3})"
                table.add_row(row["kind"], row["field"], str(row["mention_count"]), refs, srcs)
            sink.console.print(table)
            sink.console.print(
                "\n[bold]Next:[/bold] register these entity kinds in a profile, migrate the refs to "
                "registered kinds, or move non-entity annotations to [cyan]meta:*[/cyan]."
            )

        if displayed["lingering_tags_lines"]:
            with_values = [
                r for r in displayed["lingering_tags_lines"] if r["values"]
            ]
            empty_count = len(displayed["lingering_tags_lines"]) - len(with_values)

            if with_values:
                title = f"Legacy `tags:` fields to migrate ({len(with_values)})"
                table = Table(title=title)
                table.add_column("File", style="bold")
                table.add_column("Values")
                for row in with_values:
                    table.add_row(row["file"], ", ".join(row["values"]))
                sink.console.print(table)

            if empty_count:
                sink.console.print(
                    f"[dim]...and {empty_count} additional file(s) with empty "
                    "`tags: []` (cosmetic only).[/dim]"
                )

        if displayed["identity_policy"]:
            table = Table(
                title=f"Identity Policy ({len(displayed['identity_policy'])})"
            )
            table.add_column("Check", style="bold")
            table.add_column("Entity")
            table.add_column("File")
            table.add_column("Message")
            for row in displayed["identity_policy"]:
                table.add_row(
                    row["check"],
                    row["entity_id"],
                    row["source_file"],
                    row["message"],
                )
            sink.console.print(table)

        if entity_identity:
            table = Table(title=f"Entity Identity ({len(entity_identity)})")
            table.add_column("Code", style="bold", no_wrap=True, min_width=26)
            table.add_column("Severity")
            table.add_column("Path", overflow="fold")
            table.add_column("Canonical ID", overflow="fold")
            table.add_column("Message", overflow="fold")
            for row in entity_identity:
                table.add_row(
                    row["code"],
                    row["severity"],
                    row.get("path") or "",
                    row.get("canonical_id") or "",
                    row["message"],
                )
            sink.console.print(table)

        if validation:
            table = Table(title=f"Validation ({len(validation)})")
            table.add_column("Severity", style="bold")
            table.add_column("Path", overflow="fold")
            table.add_column("Rule")
            table.add_column("Task")
            table.add_column("Message", overflow="fold")
            for row in validation:
                path = row.get("path") or ""
                line = row.get("line")
                if line is not None:
                    path = f"{path}:{line}" if path else str(line)
                table.add_row(
                    row.get("severity", ""),
                    path,
                    row.get("rule") or "",
                    row.get("task") or "",
                    row.get("message", ""),
                )
            sink.console.print(table)

        adoption_table = Table(title="Layered-Claim Adoption")
        adoption_table.add_column("Check", style="bold")
        adoption_table.add_column("Coverage", justify="right")
        adoption_table.add_column("Fraction", justify="right")
        for label, metric in (
            ("Propositions with authored claim_layer", layered_claims["proposition_claim_layer_coverage"]),
            (
                "Causal-leaning propositions with authored identification_strength",
                layered_claims["causal_leaning_identification_coverage"],
            ),
        ):
            adoption_table.add_row(
                label,
                f"{metric['numerator']}/{metric['denominator']}",
                f"{metric['fraction']:.2f}",
            )
        sink.console.print(adoption_table)

        if layered_claims["migration_issues"]:
            issue_table = Table(title=f"Layered-Claim Migration Issues ({len(layered_claims['migration_issues'])})")
            issue_table.add_column("Proposition", style="bold")
            issue_table.add_column("Warnings")
            issue_table.add_column("TODOs")
            for row in layered_claims["migration_issues"]:
                issue_table.add_row(
                    row["proposition"],
                    "; ".join(row["warnings"]) or "-",
                    "; ".join(row["todos"]) or "-",
                )
            sink.console.print(issue_table)

        if layered_claims["rival_model_packets_missing_discriminating_predictions"]:
            rival_table = Table(
                title=(
                    "Rival-model packets missing discriminating predictions "
                    f"({len(layered_claims['rival_model_packets_missing_discriminating_predictions'])})"
                )
            )
            rival_table.add_column("Proposition", style="bold")
            rival_table.add_column("Packet")
            for row in layered_claims["rival_model_packets_missing_discriminating_predictions"]:
                rival_table.add_row(row["proposition"], row["packet_id"])
            sink.console.print(rival_table)

        dataset_anomalies = displayed.get("dataset_anomalies") or []
        if dataset_anomalies:
            ds_table = Table(title=f"Dataset Anomalies ({len(dataset_anomalies)})")
            ds_table.add_column("Code", style="bold")
            ds_table.add_column("Severity")
            ds_table.add_column("Entity")
            ds_table.add_column("Message")
            for row in dataset_anomalies:
                ds_table.add_row(
                    row.get("code", ""),
                    row.get("severity", ""),
                    row.get("entity_id", ""),
                    row.get("message", ""),
                )
            sink.console.print(ds_table)

        omitted = displayed.get("section_omitted") or {}
        if omitted:
            hidden = sum(omitted.values())
            sink.echo(
                f"showing {displayed['displayed_issues']} of {total_issues} issues "
                f"(severity: {severity}, cap: {SECTION_ROW_CAP}/section)"
            )
            sink.echo(f"  {hidden} finding(s) hidden — {sink.complete_via}")

    emit(
        output_format=output_format,
        payload=displayed,
        render_text=_render_report,
        sink=sink,
    )
    sink.flush()
    # This fixed-shape bounded control notice is the sole permitted sink bypass. It
    # follows a successful flush, never a finally block.
    if control_notice is not None:
        click.echo(control_notice)
