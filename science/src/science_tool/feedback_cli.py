from __future__ import annotations

from pathlib import Path
from typing import cast

import click

from science_tool.feedback import VALID_CATEGORIES, VALID_CONCERNS, VALID_STATUSES
from science_tool.output import OUTPUT_FORMATS, emit_query_rows


_FB_CATEGORIES = VALID_CATEGORIES
_FB_STATUSES = VALID_STATUSES
_FB_CONCERNS = VALID_CONCERNS


@click.group("feedback")
def feedback_group() -> None:
    """Feedback management commands."""


def _get_feedback_dir() -> Path:
    import os

    from science_tool.registry.config import get_science_config_dir

    return Path(os.environ.get("SCIENCE_FEEDBACK_DIR", str(get_science_config_dir() / "feedback")))


@feedback_group.command("add", context_settings={"allow_extra_args": True})
@click.option("--from-recent", is_flag=True, help="Use the newest eligible local telemetry event as feedback context.")
@click.option("--target", default=None, help="What the feedback is about (e.g., command:interpret-results)")
@click.option("--summary", required=True, help="One-line description")
@click.option("--category", default=None, type=click.Choice(_FB_CATEGORIES))
@click.option("--concern", default=None, type=click.Choice(_FB_CONCERNS), help="tooling (default) or a methodology:* lens")
@click.option("--detail", default=None, help="Optional prose detail")
@click.option("--project", default=None, help="Project name (auto-detected if omitted)")
@click.option("--related", multiple=True, help="Related feedback entry IDs")
@click.option("--merge-into", "merge_into", default=None, help="Record this filing as an occurrence of an existing entry ID")
@click.pass_context
def feedback_add(
    ctx: click.Context,
    from_recent: bool,
    target: str,
    summary: str,
    category: str | None,
    concern: str | None,
    detail: str | None,
    project: str | None,
    related: tuple[str, ...],
    merge_into: str | None,
) -> None:
    """Add a feedback entry."""
    from datetime import date as _date

    from science_tool.feedback import (
        FeedbackEntry,
        detect_project,
        find_duplicate,
        find_similar_open,
        load_entry,
        next_feedback_id,
        record_occurrence,
        save_entry,
    )

    fb_dir = _get_feedback_dir()
    recent_index = _parse_from_recent_index(ctx.args, from_recent=from_recent)
    if recent_index is not None:
        from science_tool.telemetry import feedback_context_from_recent_event, get_telemetry_dir, read_events

        try:
            telemetry_context = feedback_context_from_recent_event(read_events(get_telemetry_dir()), index=recent_index)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        target = target or telemetry_context.target
        category = category or telemetry_context.category
        detail = f"{detail}\n\n{telemetry_context.detail}" if detail else telemetry_context.detail

    if target is None:
        raise click.UsageError("--target is required unless --from-recent is used")
    category = category or "suggestion"
    concern = concern or "tooling"

    if project is None:
        project = detect_project(Path.cwd())

    today = _date.today().isoformat()

    # Explicit merge onto a chosen entry, or an automatic non-lossy merge onto a
    # normalized-exact duplicate. Either way the filing is *recorded* as an
    # occurrence — its project/category/detail are kept, never discarded.
    if merge_into is not None:
        merge_path = fb_dir / f"{merge_into}.yaml"
        if not merge_path.exists():
            raise click.ClickException(f"Feedback entry not found: {merge_into}")
        dup = load_entry(merge_path)
    else:
        dup = find_duplicate(fb_dir, target=target, summary=summary, concern=concern)

    if dup is not None:
        record_occurrence(dup, date=today, project=project, category=category, detail=detail)
        save_entry(fb_dir, dup)
        click.echo(f"Recorded occurrence on {dup.id} (now filed {dup.recurrence}x)")
        return

    entry_id = next_feedback_id(fb_dir, today)

    entry = FeedbackEntry(
        id=entry_id,
        created=today,
        project=project,
        target=target,
        category=category,
        summary=summary,
        detail=detail,
        related=list(related),
        concern=concern,
    )
    save_entry(fb_dir, entry)
    click.echo(f"Created {entry.id}: {entry.summary}")

    # Advisory only: surface fuzzy near-duplicates so the filer can relate or
    # merge them. Never an automatic merge — a duplicate entry is recoverable,
    # a discarded filing is not.
    neighbors = find_similar_open(
        fb_dir, target=target, summary=summary, concern=concern, exclude_id=entry.id
    )
    if neighbors:
        click.echo("Possible similar open entries (not merged):")
        for neighbor in neighbors:
            click.echo(f"  - {neighbor.id} [{neighbor.target}] {neighbor.summary}")
        click.echo("Merge with: science feedback add ... --merge-into <id>  (or link via feedback update --related)")


def _parse_from_recent_index(extra_args: list[str], *, from_recent: bool) -> int | None:
    if not from_recent:
        if extra_args:
            raise click.UsageError(f"Unexpected argument: {extra_args[0]}")
        return None
    if not extra_args:
        return 1
    if len(extra_args) > 1:
        raise click.UsageError("--from-recent accepts at most one 1-based index")
    try:
        index = int(extra_args[0])
    except ValueError as exc:
        raise click.UsageError("--from-recent index must be an integer") from exc
    if index < 1:
        raise click.UsageError("--from-recent index must be 1 or greater")
    return index


@feedback_group.command("list")
@click.option("--status", default="open", help="Filter by status (omit for 'open'; use 'all' for all statuses)")
@click.option("--target", default=None, help="Filter by target (supports fnmatch globs)")
@click.option("--category", default=None, type=click.Choice(_FB_CATEGORIES))
@click.option("--project", default=None, help="Filter by project name")
@click.option("--concern", default=None, help="Filter by concern (supports fnmatch globs, e.g. 'methodology:*')")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def feedback_list(
    status: str | None,
    target: str | None,
    category: str | None,
    project: str | None,
    concern: str | None,
    output_format: str,
    output_path: Path | None,
) -> None:
    """List feedback entries (default: open only)."""
    from science_tool.feedback import list_entries

    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    if status == "all":
        status = None

    fb_dir = _get_feedback_dir()
    entries = list_entries(fb_dir, status=status, target=target, category=category, project=project, concern=concern)

    columns = [
        ("id", "ID"),
        ("created", "Date"),
        ("project", "Project"),
        ("target", "Target"),
        ("concern", "Concern"),
        ("category", "Category"),
        ("summary", "Summary"),
        ("recurrence", "Recur"),
    ]
    rows = [
        {
            "id": e.id,
            "created": e.created,
            "project": e.project,
            "target": e.target,
            "concern": e.concern,
            "category": e.category,
            "summary": e.summary,
            "recurrence": e.recurrence,
        }
        for e in entries
    ]
    complete_via = build_complete_via(click.get_current_context(), output_hint="feedback.json")
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} feedback entries to {output_path}")
        if output_path is not None
        else None
    )
    sink = BoundedSink(
        lookup("feedback list"),
        output_path=output_path,
        command_path="feedback list",
        complete_via=complete_via,
    )
    emit_query_rows(output_format=output_format, title="Feedback", columns=columns, rows=rows, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@feedback_group.command("update")
@click.argument("entry_id")
@click.option("--status", default=None, type=click.Choice(_FB_STATUSES))
@click.option("--resolution", default=None, help="Required when setting terminal status")
@click.option("--category", default=None, type=click.Choice(_FB_CATEGORIES))
@click.option("--concern", default=None, type=click.Choice(_FB_CONCERNS))
@click.option("--summary", default=None)
@click.option("--detail", default=None)
@click.option("--related", multiple=True, help="Related feedback entry IDs")
def feedback_update(
    entry_id: str,
    status: str | None,
    resolution: str | None,
    category: str | None,
    concern: str | None,
    summary: str | None,
    detail: str | None,
    related: tuple[str, ...],
) -> None:
    """Update a feedback entry."""
    from science_tool.feedback import update_entry as _update

    fb_dir = _get_feedback_dir()
    try:
        entry = _update(
            fb_dir,
            entry_id,
            status=status,
            resolution=resolution,
            category=category,
            concern=concern,
            summary=summary,
            detail=detail,
            related=list(related) if related else None,
        )
    except (FileNotFoundError, ValueError) as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Updated {entry.id}")


@feedback_group.command("triage")
@click.option("--target", default=None, help="Filter by target (fnmatch glob)")
@click.option("--concern", default=None, help="Filter by concern (fnmatch glob)")
@click.option(
    "--cluster", "cluster_mode", is_flag=True, help="Cluster near-duplicate summaries within each target/category"
)
@click.option(
    "--since", "since_days", type=click.IntRange(min=0), default=None, help="Only include entries from the last N days"
)
@click.option("--with-telemetry", is_flag=True, help="Include recent local telemetry context.")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
def feedback_triage(
    target: str | None,
    concern: str | None,
    cluster_mode: bool,
    since_days: int | None,
    with_telemetry: bool,
    output_format: str,
) -> None:
    """Show open entries grouped or clustered for triage."""
    from science_tool.feedback import attach_telemetry_to_triage_rows, cluster_for_triage, group_for_triage

    fb_dir = _get_feedback_dir()
    if cluster_mode or output_format == "json":
        rows = cluster_for_triage(fb_dir, target=target, concern=concern, since_days=since_days)
        if with_telemetry:
            from science_tool.telemetry import get_telemetry_dir, read_events

            rows = attach_telemetry_to_triage_rows(
                rows,
                events=read_events(get_telemetry_dir()),
                since_days=since_days,
            )
        if not rows:
            if output_format == "json":
                emit_query_rows(
                    output_format=output_format,
                    title="Feedback Triage",
                    columns=[],
                    rows=[],
                    meta={"cluster": True, "since_days": since_days, "with_telemetry": with_telemetry},
                )
            else:
                click.echo("No open feedback entries.")
            return
        columns = [
            ("target", "Target"),
            ("concern", "Concern"),
            ("category", "Category"),
            ("count", "Count"),
            ("total_recurrence", "Recur"),
            ("suggested_status", "Suggested"),
            ("suggested_next_test_target", "Next test target"),
            ("representative_summary", "Summary"),
            ("entry_ids", "Entries"),
        ]
        if with_telemetry:
            columns.append(("telemetry_text", "Telemetry"))
        table_rows = rows if output_format == "json" else _feedback_triage_table_rows(rows, with_telemetry=with_telemetry)
        emit_query_rows(
            output_format=output_format,
            title="Feedback Triage",
            columns=columns,
            rows=table_rows,
            meta={"cluster": True, "since_days": since_days, "with_telemetry": with_telemetry},
        )
        return

    groups = group_for_triage(fb_dir, target=target, concern=concern)

    if not groups:
        click.echo("No open feedback entries.")
        return

    telemetry_events: list[dict[str, object]] = []
    if with_telemetry:
        from science_tool.telemetry import get_telemetry_dir, read_events

        telemetry_events = read_events(get_telemetry_dir())

    for (concern_key, target_key), group in groups.items():
        n_projects = len(group["projects"])
        n_entries = len(group["entries"])
        total_recur = group["total_recurrence"]
        projects_str = ", ".join(sorted(group["projects"])) if group["projects"] else "unknown"
        click.echo(
            f"\n## [{concern_key}] {target_key}  "
            f"({n_entries} entries, {total_recur} recurrences, {n_projects} projects: {projects_str})"
        )
        if with_telemetry:
            from science_tool.telemetry import format_feedback_telemetry, summarize_recent_for_feedback_target

            summary = summarize_recent_for_feedback_target(
                telemetry_events,
                target=group["target"],
                since_days=since_days if since_days is not None else 14,
            )
            click.echo(f"Telemetry: {format_feedback_telemetry(summary)}")
        for entry in group["entries"]:
            click.echo(f"  - {entry.id} [{entry.category}] {entry.summary}")


def _feedback_triage_table_rows(rows: list[dict[str, object]], *, with_telemetry: bool) -> list[dict[str, object]]:
    from science_tool.telemetry import format_feedback_telemetry

    table_rows: list[dict[str, object]] = []
    for row in rows:
        entry_ids = row.get("entry_ids")
        telemetry = row.get("telemetry")
        copied = dict(row)
        copied["entry_ids"] = ", ".join(str(entry_id) for entry_id in entry_ids) if isinstance(entry_ids, list) else ""
        copied["telemetry_text"] = (
            format_feedback_telemetry(cast(dict[str, object], telemetry))
            if with_telemetry and isinstance(telemetry, dict)
            else ""
        )
        table_rows.append(copied)
    return table_rows


@feedback_group.command("scaffold-test")
@click.argument("entry_id")
@click.option(
    "--out",
    "out_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Output path for the pytest scaffold; relative paths are resolved from the current directory.",
)
@click.option("--dry-run", is_flag=True, help="Print the planned output path without writing.")
@click.option("--force", is_flag=True, help="Overwrite an existing scaffold file.")
def feedback_scaffold_test(entry_id: str, out_path: Path | None, dry_run: bool, force: bool) -> None:
    """Create a failing pytest scaffold for one feedback entry."""
    from science_tool.feedback import scaffold_test_for_feedback

    fb_dir = _get_feedback_dir()
    try:
        result = scaffold_test_for_feedback(
            fb_dir,
            entry_id,
            project_root=Path.cwd(),
            out_path=out_path,
            force=force,
            dry_run=dry_run,
        )
    except (FileNotFoundError, FileExistsError) as exc:
        raise click.ClickException(str(exc)) from exc

    prefix = "[dry run] Would write" if dry_run else "Wrote"
    click.echo(f"{prefix} feedback regression scaffold: {result.path}")
    click.echo(f"Suggested existing test target: {result.suggested_test_target}")
    click.echo(f"Replace the scaffold with a real failing test before closing {entry_id}.")


@feedback_group.command("report")
@click.option("--status", default=None, help="Filter by status")
@click.option("--project", default=None, help="Filter by project name")
@click.option("--concern", default=None, help="Filter by concern (fnmatch glob)")
def feedback_report(status: str | None, project: str | None, concern: str | None) -> None:
    """Generate a markdown report of feedback entries."""
    from science_tool.feedback import render_report

    fb_dir = _get_feedback_dir()
    report = render_report(fb_dir, status=status, project=project, concern=concern)
    click.echo(report)


@feedback_group.command("targets")
@click.option("--status", default="open", help="Filter by status (omit for 'open'; use 'all' for all statuses)")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
def feedback_targets(status: str | None, output_format: str) -> None:
    """List existing feedback targets so filers reuse a spelling instead of minting a new one."""
    from science_tool.feedback import list_targets

    if status == "all":
        status = None

    fb_dir = _get_feedback_dir()
    rows = list_targets(fb_dir, status=status)
    columns = [
        ("target", "Target"),
        ("normalized", "Normalized"),
        ("count", "Entries"),
        ("total_recurrence", "Recur"),
    ]
    emit_query_rows(output_format=output_format, title="Feedback Targets", columns=columns, rows=rows)


@feedback_group.command("regression-candidates")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
def feedback_regression_candidates(output_format: str) -> None:
    """List open 'positive' entries as regression-test candidates.

    A positive records a validated property but has no consumption path of its
    own. Each row names the existing test file most likely to host the
    regression; hand an id to `science feedback scaffold-test <id>` to seed one.
    """
    from science_tool.feedback import list_regression_candidates

    fb_dir = _get_feedback_dir()
    rows = list_regression_candidates(fb_dir)
    if not rows and output_format != "json":
        click.echo("No open positive feedback to convert into regression tests.")
        return
    columns = [
        ("id", "ID"),
        ("created", "Date"),
        ("project", "Project"),
        ("target", "Target"),
        ("recurrence", "Recur"),
        ("suggested_next_test_target", "Scaffold into"),
        ("summary", "Summary"),
    ]
    emit_query_rows(output_format=output_format, title="Feedback Regression Candidates", columns=columns, rows=rows)


@feedback_group.command("show")
@click.argument("entry_id")
def feedback_show(entry_id: str) -> None:
    """Show one feedback entry in full, including every recorded occurrence."""
    from science_tool.feedback import load_entry

    fb_dir = _get_feedback_dir()
    path = fb_dir / f"{entry_id}.yaml"
    if not path.exists():
        raise click.ClickException(f"Feedback entry not found: {entry_id}")
    entry = load_entry(path)
    import yaml

    click.echo(yaml.dump(entry.model_dump(mode="json"), default_flow_style=False, sort_keys=False))
