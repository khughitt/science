"""`science explore-ideas` command group — apply/inspect exploration reports."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from science_tool.budget.sink import BoundedSink

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


@click.group("explore-ideas")
def explore_ideas_group() -> None:
    """Explore-ideas commands."""


def _apply_truncation(full: dict[str, Any], displayed: dict[str, Any], complete_via: str) -> dict[str, Any] | None:
    """Aggregate the per-list ``<key>_omitted`` markers `project_explore_ideas_apply` left.

    Several lists can each be truncated in the same run, so this collects all of them
    into one ``truncation`` block rather than the single-list-report ``omitted``/``total``
    pair -- a payload with only one such pair could name only one truncated list.
    """
    omitted = {key[: -len("_omitted")]: displayed[key] for key in displayed if key.endswith("_omitted")}
    if not omitted:
        return None
    return {
        "omitted": omitted,
        "total": {key: len(full[key]) for key in omitted},
        "complete_via": complete_via,
    }


def _echo_decision_notes(sink: BoundedSink, displayed: dict[str, Any]) -> None:
    """Print the triage rationale each block recorded.

    A bare `decision: drop` token loses why the block was rejected -- a considered
    rejection and an oversight read identically to a later reader. Notes are
    printed together rather than beside their own decision bucket, so scanning
    the reasoning does not mean scanning four lists.
    """
    for item in displayed.get("decision_notes", []):
        sink.echo(f"  note {item['candidate_id']}: {item['note']}")
    omitted = displayed.get("decision_notes_omitted")
    if omitted:
        sink.echo(f"  ({omitted} further decision note(s) omitted)")


def _echo_apply_truncation_footer(sink: BoundedSink, displayed: dict[str, Any]) -> None:
    truncation = displayed.get("truncation")
    if not truncation:
        return
    for key, omitted in truncation["omitted"].items():
        total = truncation["total"][key]
        sink.echo(f"showing {total - omitted} of {total} {key}")
    sink.echo(f"  complete output:  {truncation['complete_via']}")


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
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted report to PATH instead of stdout.",
)
@click.option(
    "--show-preexisting",
    "show_preexisting",
    is_flag=True,
    default=False,
    help="List each created entity's pre-existing project audit failures individually "
    "instead of summarizing them",
)
def explore_ideas_apply(
    from_value: str,
    model_id: str,
    check_only: bool,
    output_format: str,
    output_path: Path | None,
    show_preexisting: bool,
) -> None:
    """Apply kept candidates from an exploration report to real entities."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.explore_ideas_projection import project_explore_ideas_apply

    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("explore-ideas-apply", output_format)
    )
    sink = BoundedSink(
        lookup("explore-ideas apply"), output_path=output_path, command_path="explore-ideas apply",
        complete_via=complete_via,
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete apply report to {output_path}")
        if output_path is not None
        else None
    )

    try:
        if check_only:
            check_result = check_report(Path.cwd(), from_value, model_id)
            full: dict[str, Any] = check_result.to_dict()
            displayed = (
                full
                if output_path is not None
                else project_explore_ideas_apply(full, show_preexisting=show_preexisting)
            )
            if output_path is None:
                truncation = _apply_truncation(full, displayed, complete_via)
                if truncation is not None:
                    displayed = {**displayed, "truncation": truncation}

            def _render_check() -> None:
                sink.echo(
                    f"{len(check_result.to_create)} would create, "
                    f"{len(check_result.skipped_applied)} already applied, "
                    f"{len(check_result.skipped_other)} deferred/dropped, "
                    f"{len(check_result.manual)} to apply manually, "
                    f"{len(check_result.folds)} to fold manually"
                )
                for plan in displayed["to_create"]:
                    slug = f" slug={plan['slug']}" if plan["slug"] else ""
                    sink.echo(f"  would create {plan['candidate_id']} ({plan['kind']}){slug}")
                for candidate_id in displayed["skipped_applied"]:
                    sink.echo(f"  already applied: {candidate_id}")
                for candidate_id in displayed["skipped_other"]:
                    sink.echo(f"  skipped drop/defer: {candidate_id}")
                for item in displayed["manual"]:
                    sink.echo(f"  apply manually ({item['proposed_kind']}): {item['candidate_id']}")
                for fold in displayed["folds"]:
                    sink.echo(f"  fold manually: {fold['candidate_id']} -> {', '.join(fold['targets'])}")
                _echo_decision_notes(sink, displayed)
                _echo_apply_truncation_footer(sink, displayed)

            emit(output_format=output_format, payload=displayed, render_text=_render_check, sink=sink)
            sink.flush()
            if control_notice is not None:
                click.echo(control_notice)
            return
        result = apply_report(Path.cwd(), from_value, model_id, date.today())
    except (ApplyValidationError, ApplyWriteBackError) as exc:
        raise click.ClickException(str(exc)) from exc

    full: dict[str, Any] = result.to_dict()
    displayed = (
        full if output_path is not None else project_explore_ideas_apply(full, show_preexisting=show_preexisting)
    )
    if output_path is None:
        truncation = _apply_truncation(full, displayed, complete_via)
        if truncation is not None:
            displayed = {**displayed, "truncation": truncation}

    def _render_result() -> None:
        sink.echo(
            f"{len(result.created)} created, "
            f"{len(result.skipped_applied)} already applied, "
            f"{len(result.skipped_other)} deferred/dropped, "
            f"{len(result.manual)} to apply manually, "
            f"{len(result.folds)} to fold manually, "
            f"{len(result.failures)} failed"
        )
        for created in displayed["created"]:
            sink.echo(f"  created {created['candidate_id']} -> {created['entity_id']} ({created['kind']})")
        for candidate_id in displayed["skipped_applied"]:
            sink.echo(f"  already applied: {candidate_id}")
        for candidate_id in displayed["skipped_other"]:
            sink.echo(f"  skipped drop/defer: {candidate_id}")
        for item in displayed["manual"]:
            sink.echo(f"  apply manually ({item['proposed_kind']}): {item['candidate_id']}")
        for fold in displayed["folds"]:
            sink.echo(f"  fold manually: {fold['candidate_id']} -> {', '.join(fold['targets'])}")
        for item in displayed["failures"]:
            sink.echo(f"  FAILED {item['candidate_id']}: {item['error']}")
        _echo_decision_notes(sink, displayed)
        for created in displayed["created"]:
            for warning in created["warnings"]:
                sink.echo(f"WARNING: {warning}")
            preexisting_note = created.get("preexisting_warnings_note")
            if preexisting_note is not None:
                sink.echo(preexisting_note)
        _echo_apply_truncation_footer(sink, displayed)

    emit(output_format=output_format, payload=displayed, render_text=_render_result, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)

    if result.failures:
        raise SystemExit(1)


def _render_gap_result_text(full: dict[str, Any], displayed: dict[str, Any], sink: BoundedSink) -> None:
    counts = full["counts"]
    sink.echo(
        f"{counts['entities']} applied entities inspected, "
        f"{counts['gaps']} gaps ({counts['errors']} errors, {counts['warnings']} warnings)"
    )
    for entity in displayed["entities"]:
        if not entity["gaps"]:
            continue
        label = entity["entity_id"] or "<missing applied_as>"
        kind = entity["kind"] or "unknown"
        sink.echo("")
        sink.echo(f"{entity['candidate_id']} -> {label} ({kind})")
        for gap in entity["gaps"]:
            sink.echo(f"  {gap['severity'].upper()} {gap['code']}: {gap['message']}")
            sink.echo(f"    next: {gap['suggested_action']}")
    if displayed.get("entities_omitted", 0):
        sink.echo(f"showing {len(displayed['entities'])} of {len(full['entities'])} entities")
        sink.echo(f"  complete output:  {sink.complete_via}")


@explore_ideas_group.command("gaps")
@click.option("--from", "from_value", required=True, help="Report file path, or report id (basename stem).")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted report to PATH instead of stdout.",
)
def explore_ideas_gaps(from_value: str, output_format: str, output_path: Path | None) -> None:
    """Inspect applied exploration entities for deterministic follow-up gaps."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_single_list_report
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    try:
        result = inspect_gaps_report(Path.cwd(), from_value)
    except ApplyValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("explore-ideas-gaps", output_format)
    )
    sink = BoundedSink(
        lookup("explore-ideas gaps"), output_path=output_path, command_path="explore-ideas gaps",
        complete_via=complete_via,
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete gap report to {output_path}")
        if output_path is not None
        else None
    )

    full: dict[str, Any] = result.to_dict()
    displayed = full if output_path is not None else project_single_list_report(full, "entities", 40)
    if output_path is None and displayed.get("entities_omitted", 0):
        displayed = {
            **displayed,
            "truncation": {
                "omitted": displayed["entities_omitted"],
                "total": len(full["entities"]),
                "complete_via": complete_via,
            },
        }

    emit(
        output_format=output_format,
        payload=displayed,
        render_text=lambda: _render_gap_result_text(full, displayed, sink),
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@explore_ideas_group.command("resolve-anchors")
@click.option("--from", "from_value", required=True, help="Report file path, or report id (basename stem).")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted report to PATH instead of stdout.",
)
def explore_ideas_resolve_anchors(from_value: str, output_format: str, output_path: Path | None) -> None:
    """Resolve report literature anchors against papers and references.bib."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_single_list_report
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    try:
        result = resolve_anchors_report(Path.cwd(), from_value)
    except ApplyValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("explore-ideas-resolve-anchors", output_format)
    )
    sink = BoundedSink(
        lookup("explore-ideas resolve-anchors"), output_path=output_path,
        command_path="explore-ideas resolve-anchors", complete_via=complete_via,
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete anchor-resolution report to {output_path}")
        if output_path is not None
        else None
    )

    full: dict[str, Any] = result.to_dict()
    displayed = full if output_path is not None else project_single_list_report(full, "anchors", 40)
    if output_path is None and displayed.get("anchors_omitted", 0):
        displayed = {
            **displayed,
            "truncation": {
                "omitted": displayed["anchors_omitted"],
                "total": len(full["anchors"]),
                "complete_via": complete_via,
            },
        }

    def _render() -> None:
        counts = full["counts"]
        sink.echo(
            f"{counts['resolved']} resolved, "
            f"{counts['already_resolved']} already resolved, "
            f"{counts['ambiguous']} ambiguous, "
            f"{counts['unresolved']} unresolved, "
            f"{counts['mismatch']} mismatch"
        )
        # The identity headline, stated separately from the status breakdown:
        # the run that prompted this confirmed 2 of 49 anchors, a fact the
        # per-status tally alone does not put in front of the reader.
        total_anchors = counts["verified"] + counts["unverified"]
        sink.echo(
            f"identity: {counts['verified']} of {total_anchors} verified against a real record; "
            f"{counts['unverified']} unverified (model-asserted, nothing confirms them)"
        )
        for row in displayed["anchors"]:
            label = f"{row['candidate_id']}[{row['anchor_index']}]"
            if row["status"] == "resolved":
                sink.echo(f"  {label} -> {row['resolved']} ({row['match_kind']})")
            elif row["status"] == "already-resolved":
                sink.echo(f"  {label} already resolved: {row['resolved']}")
            elif row["status"] == "ambiguous":
                sink.echo(f"  {label} ambiguous {row['match_kind']}: {', '.join(row['candidates'])}")
            elif row["status"] == "mismatch":
                sink.echo(f"  {label} MISMATCH {row['resolved']} ({row['match_kind']}): {row['detail']}")
            else:
                sink.echo(f"  {label} unresolved: {row['query']}")
        if displayed.get("anchors_omitted", 0):
            sink.echo(f"showing {len(displayed['anchors'])} of {len(full['anchors'])} anchors")
            sink.echo(f"  complete output:  {sink.complete_via}")

    emit(output_format=output_format, payload=displayed, render_text=_render, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


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


@explore_ideas_group.command("seed-coverage")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    envvar="SCIENCE_PROJECT_ROOT",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", show_default=True)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted diagnostic to PATH instead of stdout.",
)
def explore_ideas_seed_coverage(project_root: Path, output_format: str, output_path: Path | None) -> None:
    """Report how representative the Phase-1 brief seed is, and where its scope came from."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_single_list_report
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.explore_ideas_seed import SCOPE_DECLARED, compute_seed_coverage
    from science_tool.topic_coverage import MalformedTopicError

    try:
        seed = compute_seed_coverage(project_root)
    except MalformedTopicError as exc:
        raise click.ClickException(str(exc)) from exc

    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("explore-ideas-seed-coverage", output_format)
    )
    sink = BoundedSink(
        lookup("explore-ideas seed-coverage"),
        output_path=output_path,
        command_path="explore-ideas seed-coverage",
        complete_via=complete_via,
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete seed-coverage diagnostic to {output_path}")
        if output_path is not None
        else None
    )

    full: dict[str, Any] = seed.to_dict()
    displayed = full if output_path is not None else project_single_list_report(full, "topics", 40)

    def _render() -> None:
        if displayed["n_topics"] == 0:
            sink.echo("topics: 0 (no topics)")
        else:
            warn = "  ⚠ stub-dominated" if displayed["stub_dominated"] else ""
            sink.echo(
                f"topics: {displayed['n_topics']} (substantive {displayed['n_substantive']}, "
                f"stubs {displayed['n_topics'] - displayed['n_substantive']}) — "
                f"stub_ratio {displayed['stub_ratio']:.2f}{warn}"
            )
        sink.echo(f"scope_source: {displayed['scope_source']}")
        for source in displayed["brief_sources"]:
            if source["source"] == SCOPE_DECLARED:
                layout = "" if source["layout"] == "canonical" else f" [{source['layout']} layout, unmigrated]"
                sink.echo(f"  {source['name']}: {source['path']}{layout}")
            else:
                sink.echo(f"  {source['name']}: absent — the brief cannot cite a declared boundary")
        if displayed.get("topics_omitted", 0):
            sink.echo(f"  showing {len(displayed['topics'])} of {len(full['topics'])} topics")
            sink.echo(f"  complete output:  {complete_via}")

    emit(output_format=output_format, payload=displayed, render_text=_render, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
