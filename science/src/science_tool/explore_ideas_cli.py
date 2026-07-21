"""`science explore-ideas` command group — apply/inspect exploration reports."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import click

from science_tool.explore_ideas import (
    ApplyValidationError,
    ApplyWriteBackError,
    apply_report,
    backfill_lens_views,
    check_report,
    inspect_gaps_report,
    resolve_anchors_report,
)
from science_tool.output import emit
from science_tool.typed_entity_cli import emit_entity_warnings


@click.group("explore-ideas")
def explore_ideas_group() -> None:
    """Explore-ideas commands."""


@explore_ideas_group.command("apply")
@click.option("--from", "from_value", required=True, help="Report file path, or report id (basename stem).")
@click.option("--model-id", "model_id", required=True, help="Model id for the --added-by provenance stamp.")
@click.option("--check", "check_only", is_flag=True, help="Validate and summarize the apply plan without writing.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def explore_ideas_apply(from_value: str, model_id: str, check_only: bool, output_format: str) -> None:
    """Apply kept candidates from an exploration report to real entities."""
    try:
        if check_only:
            check_result = check_report(Path.cwd(), from_value, model_id)

            def _render_check() -> None:
                click.echo(
                    f"{len(check_result.to_create)} would create, "
                    f"{len(check_result.skipped_applied)} already applied, "
                    f"{len(check_result.skipped_other)} deferred/dropped, "
                    f"{len(check_result.manual)} to apply manually, "
                    f"{len(check_result.folds)} to fold manually"
                )
                for plan in check_result.to_create:
                    click.echo(f"  would create {plan.candidate_id} ({plan.kind})")
                for candidate_id in check_result.skipped_applied:
                    click.echo(f"  already applied: {candidate_id}")
                for candidate_id in check_result.skipped_other:
                    click.echo(f"  skipped drop/defer: {candidate_id}")
                for candidate_id, kind in check_result.manual:
                    click.echo(f"  apply manually ({kind}): {candidate_id}")
                for fold in check_result.folds:
                    click.echo(f"  fold manually: {fold.candidate_id} -> {', '.join(fold.targets)}")

            emit(output_format=output_format, payload=check_result.to_dict(), render_text=_render_check)
            return
        result = apply_report(Path.cwd(), from_value, model_id, date.today())
    except (ApplyValidationError, ApplyWriteBackError) as exc:
        raise click.ClickException(str(exc)) from exc

    def _render_result() -> None:
        click.echo(
            f"{len(result.created)} created, "
            f"{len(result.skipped_applied)} already applied, "
            f"{len(result.skipped_other)} deferred/dropped, "
            f"{len(result.manual)} to apply manually, "
            f"{len(result.folds)} to fold manually, "
            f"{len(result.failures)} failed"
        )
        for created in result.created:
            click.echo(f"  created {created.candidate_id} -> {created.entity_id} ({created.kind})")
        for candidate_id in result.skipped_applied:
            click.echo(f"  already applied: {candidate_id}")
        for candidate_id in result.skipped_other:
            click.echo(f"  skipped drop/defer: {candidate_id}")
        for candidate_id, kind in result.manual:
            click.echo(f"  apply manually ({kind}): {candidate_id}")
        for fold in result.folds:
            click.echo(f"  fold manually: {fold.candidate_id} -> {', '.join(fold.targets)}")
        for candidate_id, error in result.failures:
            click.echo(f"  FAILED {candidate_id}: {error}")
        for created in result.created:
            emit_entity_warnings(created.warnings)

    emit(output_format=output_format, payload=result.to_dict(), render_text=_render_result)

    if result.failures:
        raise SystemExit(1)


def _render_gap_result_text(result) -> None:
    counts = result.counts
    click.echo(
        f"{counts['entities']} applied entities inspected, "
        f"{counts['gaps']} gaps ({counts['errors']} errors, {counts['warnings']} warnings)"
    )
    for entity in result.entities:
        if not entity.gaps:
            continue
        label = entity.entity_id or "<missing applied_as>"
        kind = entity.kind or "unknown"
        click.echo("")
        click.echo(f"{entity.candidate_id} -> {label} ({kind})")
        for gap in entity.gaps:
            click.echo(f"  {gap.severity.upper()} {gap.code}: {gap.message}")
            click.echo(f"    next: {gap.suggested_action}")


@explore_ideas_group.command("gaps")
@click.option("--from", "from_value", required=True, help="Report file path, or report id (basename stem).")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def explore_ideas_gaps(from_value: str, output_format: str) -> None:
    """Inspect applied exploration entities for deterministic follow-up gaps."""
    try:
        result = inspect_gaps_report(Path.cwd(), from_value)
    except ApplyValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    emit(output_format=output_format, payload=result.to_dict(), render_text=lambda: _render_gap_result_text(result))


@explore_ideas_group.command("resolve-anchors")
@click.option("--from", "from_value", required=True, help="Report file path, or report id (basename stem).")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def explore_ideas_resolve_anchors(from_value: str, output_format: str) -> None:
    """Resolve report literature anchors against papers and references.bib."""
    try:
        result = resolve_anchors_report(Path.cwd(), from_value)
    except ApplyValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    def _render() -> None:
        counts = result.counts
        click.echo(
            f"{counts['resolved']} resolved, "
            f"{counts['already_resolved']} already resolved, "
            f"{counts['ambiguous']} ambiguous, "
            f"{counts['unresolved']} unresolved, "
            f"{counts['mismatch']} mismatch"
        )
        for row in result.anchors:
            label = f"{row.candidate_id}[{row.anchor_index}]"
            if row.status == "resolved":
                click.echo(f"  {label} -> {row.resolved} ({row.match_kind})")
            elif row.status == "already-resolved":
                click.echo(f"  {label} already resolved: {row.resolved}")
            elif row.status == "ambiguous":
                click.echo(f"  {label} ambiguous {row.match_kind}: {', '.join(row.candidates)}")
            elif row.status == "mismatch":
                click.echo(f"  {label} MISMATCH {row.resolved} ({row.match_kind}): {row.detail}")
            else:
                click.echo(f"  {label} unresolved: {row.query}")

    emit(output_format=output_format, payload=result.to_dict(), render_text=_render)


@explore_ideas_group.command("backfill-lens-views")
@click.option("--from", "from_value", required=True, help="Report file path, or report id (basename stem).")
def explore_ideas_backfill_lens_views(from_value: str) -> None:
    """Backfill lens_views onto entities from a prior applied report."""
    try:
        touched = backfill_lens_views(Path.cwd(), from_value, date.today())
    except (ApplyValidationError, ApplyWriteBackError) as exc:
        raise click.ClickException(str(exc)) from exc
    for entity_id, n in touched:
        click.echo(f"  {entity_id}: +{n} lens_view(s)")
    click.echo(f"backfilled {sum(n for _, n in touched)} view(s) across {len(touched)} entit(ies)")
