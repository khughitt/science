"""`science health` command — aggregate project diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import cast

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
def health_command(
    project_root: Path,
    output_format: str,
    timings: bool,
    fast: bool,
    checks: tuple[str, ...],
    skip_checks: tuple[str, ...],
    list_checks: bool,
) -> None:
    """Aggregate diagnostics for the project: unresolved refs, lingering tags, etc."""
    from rich.table import Table

    from science_tool.graph.health import build_health_report, list_health_checks
    from science_tool.styles import get_console

    project_root = project_root.resolve()
    if list_checks:
        available_checks = list_health_checks()

        def _render_checks() -> None:
            table = Table(title="Health checks")
            table.add_column("Name", style="bold")
            table.add_column("Requires sources")
            table.add_column("Description")
            for row in available_checks:
                table.add_row(str(row["name"]), "yes" if row["requires_sources"] else "no", str(row["description"]))
            get_console().print(table)

        emit(output_format=output_format, payload={"checks": available_checks}, render_text=_render_checks)
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

    def _render_report() -> None:
        if timings:
            meta = report.get("_meta") or {}
            timing_rows = meta.get("timings") or []
            total_duration = meta.get("total_duration_seconds")
            click.echo("Health timings:", err=True)
            for row in timing_rows:
                click.echo(f"  {row['name']}: {row['duration_seconds']:.3f}s", err=True)
            if isinstance(total_duration, int | float):
                click.echo(f"  total: {total_duration:.3f}s", err=True)

        layered_claims = report["layered_claims"]
        archive_lag = report["archive_lag"]
        archive_lag_total = report["archive_lag_total"]

        managed_artifacts = report.get("managed_artifacts") or []
        tooling_scaffold = report.get("tooling_scaffold") or []
        agent_context = report.get("agent_context") or []
        unregistered_ref_kinds = report.get("unregistered_ref_kinds") or []
        entity_identity = report.get("entity_identity") or []
        schema_invalid = report.get("schema_invalid") or []
        validation = report.get("validation") or []
        accepted_validation = report.get("accepted_validation") or []
        prose_epistemics = report.get("prose_epistemics") or {}
        raw_prose_epistemics_findings = prose_epistemics.get("findings") if isinstance(prose_epistemics, dict) else None
        prose_epistemics_findings: list[dict[str, object]] = (
            [cast("dict[str, object]", row) for row in raw_prose_epistemics_findings if isinstance(row, dict)]
            if isinstance(raw_prose_epistemics_findings, list)
            else []
        )
        cross_paper_evidence = report.get("cross_paper_evidence") or {}
        raw_cross_paper_findings = cross_paper_evidence.get("findings") if isinstance(cross_paper_evidence, dict) else None
        cross_paper_findings: list[dict[str, object]] = (
            [cast("dict[str, object]", row) for row in raw_cross_paper_findings if isinstance(row, dict)]
            if isinstance(raw_cross_paper_findings, list)
            else []
        )

        total_issues = report["total_issues"]
        if total_issues == 0:
            click.echo("Project is clean — no issues found.")
            if accepted_validation:
                click.echo(f"Accepted validation warnings: {len(accepted_validation)}")
            return

        console = get_console()

        if archive_lag_total:
            lag_table = Table(title="Tasks Archive Lag")
            lag_table.add_column("Metric", style="bold")
            lag_table.add_column("Count", justify="right")
            for key in ("done_in_active", "retired_in_active", "missing_completed"):
                lag_table.add_row(key, str(archive_lag[key]))
            console.print(lag_table)
            console.print(
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
            console.print(ma_table)
            console.print(
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
            console.print(ts_table)
            console.print(
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
            console.print(ac_table)
            console.print(
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
            console.print(si_table)
            console.print(
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
            console.print(pe_table)
            console.print(f"\n[bold]Next:[/bold] run [cyan]{prose_epistemics_next}[/cyan].")

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
            console.print(cpe_table)
            console.print("\n[bold]Next:[/bold] fix stale promoted_to refs or proposition source_refs, then rerun health.")

        if report["unresolved_refs"]:
            table = Table(title=f"Unresolved references ({len(report['unresolved_refs'])})")
            table.add_column("Target", style="bold")
            table.add_column("Mentions", justify="right")
            table.add_column("Suggested triage")
            table.add_column("Sources (first 3)")
            for row in report["unresolved_refs"]:
                srcs = ", ".join(row["sources"][:3])
                if len(row["sources"]) > 3:
                    srcs += f", … (+{len(row['sources']) - 3})"
                table.add_row(row["target"], str(row["mention_count"]), row["looks_like"], srcs)
            console.print(table)

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
            console.print(table)
            console.print(
                "\n[bold]Next:[/bold] register these entity kinds in a profile, migrate the refs to "
                "registered kinds, or move non-entity annotations to [cyan]meta:*[/cyan]."
            )

        if report["lingering_tags_lines"]:
            with_values = [r for r in report["lingering_tags_lines"] if r["values"]]
            empty_count = len(report["lingering_tags_lines"]) - len(with_values)

            if with_values:
                title = f"Legacy `tags:` fields to migrate ({len(with_values)})"
                table = Table(title=title)
                table.add_column("File", style="bold")
                table.add_column("Values")
                for row in with_values:
                    table.add_row(row["file"], ", ".join(row["values"]))
                console.print(table)

            if empty_count:
                console.print(f"[dim]...and {empty_count} additional file(s) with empty `tags: []` (cosmetic only).[/dim]")

        if report["identity_policy"]:
            table = Table(title=f"Identity Policy ({len(report['identity_policy'])})")
            table.add_column("Check", style="bold")
            table.add_column("Entity")
            table.add_column("File")
            table.add_column("Message")
            for row in report["identity_policy"]:
                table.add_row(row["check"], row["entity_id"], row["source_file"], row["message"])
            console.print(table)

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
            console.print(table)

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
            console.print(table)

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
        console.print(adoption_table)

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
            console.print(issue_table)

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
            console.print(rival_table)

        dataset_anomalies = report.get("dataset_anomalies") or []
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
            console.print(ds_table)

    emit(output_format=output_format, payload=report, render_text=_render_report)
