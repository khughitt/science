"""`science tasks` command group — research/dev task backlog management."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import click

from science_tool.output import OUTPUT_FORMATS, emit, emit_query_rows


DEFAULT_TASKS_DIR = Path("tasks")


@click.group("tasks")
def tasks_group() -> None:
    """Task management commands."""


@tasks_group.command("add")
@click.argument("title")
@click.option("--priority", required=True, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option("--aspects", "aspects", multiple=True)
@click.option("--related", multiple=True)
@click.option("--blocked-by", multiple=True)
@click.option("--group", default="")
@click.option("--description", default="")
@click.option("--force", is_flag=True, help="Record blockers even if entity not yet known")
def tasks_add(
    title: str,
    priority: str,
    aspects: tuple[str, ...],
    related: tuple[str, ...],
    blocked_by: tuple[str, ...],
    group: str,
    description: str,
    force: bool,
) -> None:
    """Add a new task."""
    from science_tool.tasks import TaskAspectValidationError, add_task, validate_task_aspects
    from science_tool.tasks_blockers import BlockerValidationError

    validated_aspects: list[str] = []
    if aspects:
        try:
            validated_aspects = validate_task_aspects(list(aspects))
        except TaskAspectValidationError as exc:
            raise click.ClickException(str(exc)) from exc

    try:
        task = add_task(
            project_root=Path.cwd(),
            tasks_dir=DEFAULT_TASKS_DIR,
            title=title,
            priority=priority,
            aspects=validated_aspects or None,
            related=list(related) or None,
            blocked_by=list(blocked_by) or None,
            group=group,
            description=description,
            force=force,
        )
    except BlockerValidationError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Created [{task.id}] {task.title}")


def _warn_dangling_task_refs(tasks_dir: Path) -> None:
    """Post-write self-check: surface any blocked-by/parent task ref that no
    longer resolves, so a dropped sibling is caught here rather than at graph build."""
    from science_tool.tasks import find_dangling_task_refs

    dangling = find_dangling_task_refs(tasks_dir)
    if not dangling:
        return
    for task_id, refs in sorted(dangling.items()):
        click.echo(
            f"WARNING: task {task_id} references unresolved task(s): {', '.join(refs)}",
            err=True,
        )


@tasks_group.command("done")
@click.argument("task_id")
@click.option("--note", default=None)
def tasks_done(task_id: str, note: str | None) -> None:
    """Mark a task as done."""
    from science_tool.tasks import complete_task

    try:
        task = complete_task(DEFAULT_TASKS_DIR, task_id, note=note)
    except KeyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"[{task.id}] marked done")
    _warn_dangling_task_refs(DEFAULT_TASKS_DIR)


@tasks_group.command("defer")
@click.argument("task_id")
@click.option("--reason", default=None)
def tasks_defer(task_id: str, reason: str | None) -> None:
    """Defer a task."""
    from science_tool.tasks import defer_task

    try:
        task = defer_task(DEFAULT_TASKS_DIR, task_id, reason=reason)
    except KeyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"[{task.id}] deferred")


@tasks_group.command("retire")
@click.argument("task_id")
@click.option("--reason", default=None)
def tasks_retire(task_id: str, reason: str | None) -> None:
    """Retire a task (closed without completion — no longer a priority)."""
    from science_tool.tasks import retire_task

    try:
        task = retire_task(DEFAULT_TASKS_DIR, task_id, reason=reason)
    except KeyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"[{task.id}] retired")
    _warn_dangling_task_refs(DEFAULT_TASKS_DIR)


@tasks_group.command("block")
@click.argument("task_id")
@click.option(
    "--by",
    "blocked_by",
    multiple=True,
    required=True,
    help="Typed blocker ref (repeatable): <kind>:<local-id> or <peer>:<kind>:<local-id>",
)
@click.option("--force", is_flag=True, help="Record blocker even if entity not yet known")
def tasks_block(task_id: str, blocked_by: tuple[str, ...], force: bool) -> None:
    """Block a task by one or more typed entity references."""
    from science_tool.tasks import block_task
    from science_tool.tasks_blockers import BlockerValidationError
    from science_tool.tasks_readiness import make_project_entity_lookup

    try:
        task = block_task(
            project_root=Path.cwd(),
            tasks_dir=DEFAULT_TASKS_DIR,
            task_id=task_id,
            blocked_by=list(blocked_by),
            force=force,
        )
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    except BlockerValidationError as exc:
        raise click.ClickException(str(exc)) from exc

    if force:
        try:
            lookup = cast(Callable[[str], object | None], make_project_entity_lookup(Path.cwd()))
        except ValueError:
            lookup = _missing_project_entity_lookup

        for ref in blocked_by:
            if lookup(ref) is None:
                click.echo(
                    f"WARNING: recorded unresolved blocker {ref}; graph audit will flag it",
                    err=True,
                )

    refs = ", ".join(task.blocked_by)
    click.echo(f"[{task.id}] blocked by {refs}")


def _missing_project_entity_lookup(_ref: str) -> object | None:
    return None


@tasks_group.command("blockers")
@click.argument("task_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
def tasks_blockers(task_id: str, fmt: str) -> None:
    """Show per-blocker readiness for a task."""
    from science_tool.tasks import _find_task, _read_active
    from science_tool.tasks_readiness import make_project_resolver

    tasks = _read_active(DEFAULT_TASKS_DIR)
    try:
        task = _find_task(tasks, task_id)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        resolver = make_project_resolver()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    rows = []
    for ref in task.blocked_by:
        readiness = resolver.resolve_ref(ref)
        rows.append(
            {
                "ref": ref,
                "ready": readiness.ready,
                "state": readiness.state,
                "detail": readiness.detail,
                "unresolved": readiness.state == "unresolved",
            }
        )

    def _render() -> None:
        click.echo(f"Blockers for [{task.id}] {task.title}:")
        for row in rows:
            marker = "✓" if row["ready"] else "·"
            line = f"  {marker} {row['ref']:40s}  {row['state']}"
            if row["detail"]:
                line += f"  ({row['detail']})"
            click.echo(line)

    emit(output_format=fmt, payload={"task_id": task.id, "blockers": rows}, render_text=_render)


@tasks_group.command("fix-blockers")
@click.option("--dry-run", is_flag=True, help="List legacy untyped blockers without modifying any files")
def tasks_fix_blockers(dry_run: bool) -> None:
    """Interactive sweep to retype legacy untyped blockers."""
    from science_tool.tasks import (
        _write_active,
        parse_tasks_for_cli,
    )
    from science_tool.tasks_blockers import is_typed_ref

    tasks_path = DEFAULT_TASKS_DIR / "active.md"
    tasks_, warnings = parse_tasks_for_cli(tasks_path)
    if not warnings:
        click.echo("No legacy untyped blockers found.")
        return

    if dry_run:
        click.echo("Legacy untyped blockers (dry-run):")
        for w in warnings:
            click.echo(f"  {w}")
        return

    changed = False
    for task in tasks_:
        new_blockers: list[str] = []
        for ref in task.blocked_by:
            if is_typed_ref(ref):
                new_blockers.append(ref)
                continue
            click.echo(f"\nTask [{task.id}] {task.title}")
            click.echo(f"  legacy blocker: {ref!r}")
            replacement = click.prompt(
                "  replace with (typed ref, or empty to drop, or '!' to keep as-is)",
                default="",
                show_default=False,
            ).strip()
            if replacement == "!":
                new_blockers.append(ref)
            elif replacement == "":
                changed = True  # drop
            else:
                if not is_typed_ref(replacement):
                    click.echo(f"  ! {replacement!r} not a typed ref; keeping original")
                    new_blockers.append(ref)
                else:
                    new_blockers.append(replacement)
                    changed = True
        task.blocked_by = new_blockers

    if changed and click.confirm("\nWrite changes to tasks/active.md?", default=True):
        _write_active(DEFAULT_TASKS_DIR, tasks_)
        click.echo("Updated.")
    else:
        click.echo("No changes written.")


@tasks_group.command("unblock")
@click.argument("task_id")
def tasks_unblock(task_id: str) -> None:
    """Unblock a task."""
    from science_tool.tasks import unblock_task

    try:
        task = unblock_task(DEFAULT_TASKS_DIR, task_id)
    except KeyError as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"[{task.id}] unblocked → active")


@tasks_group.command("archive")
@click.option("--apply", "do_apply", is_flag=True, help="Write changes to disk (default is dry-run).")
@click.option(
    "--check",
    is_flag=True,
    help="Print archivable counts and exit non-zero when lag is present (used by science health).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
@click.option(
    "--tasks-dir",
    default=DEFAULT_TASKS_DIR,
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
def tasks_archive(do_apply: bool, check: bool, output_format: str, tasks_dir: Path) -> None:
    """Move done/retired tasks from active.md to done/YYYY-MM.md.

    Default is dry-run: prints the planned moves without touching disk.
    Pass --apply to perform the writes (idempotent on re-run).
    """
    from science_tool.tasks_archive import apply_archive, count_archivable, plan_archive

    if check:
        counts = count_archivable(tasks_dir)
        emit_query_rows(
            output_format=output_format,
            title="Tasks Archive Lag",
            columns=[("metric", "Metric"), ("count", "Count")],
            rows=[{"metric": k, "count": v} for k, v in counts.items()],
        )
        if any(counts.values()):
            ctx = click.get_current_context()
            ctx.exit(1)
        return

    plan = plan_archive(tasks_dir)

    rows: list[dict[str, Any]] = [
        {
            "id": entry.task.id,
            "status": entry.task.status,
            "destination": str(entry.destination),
            "missing_completed": entry.missing_completed,
        }
        for entry in plan.entries
    ]

    emit_query_rows(
        output_format=output_format,
        title="Tasks Archive Plan",
        columns=[
            ("id", "ID"),
            ("status", "Status"),
            ("destination", "Destination"),
            ("missing_completed", "Missing completed:"),
        ],
        rows=rows,
    )

    for entry in plan.entries:
        if entry.missing_completed:
            click.echo(
                f"WARNING: [{entry.task.id}] has no `completed:` date; "
                f"routed to current month {entry.destination.name}",
                err=True,
            )

    for parse_error in plan.parse_errors:
        click.echo(
            f"WARNING: parse error in {parse_error.heading!r}: {parse_error.message}",
            err=True,
        )

    if not do_apply:
        if output_format != "json":
            click.echo(f"Mode: dry-run — would move {len(plan.entries)} task(s)")
        return

    if plan.parse_errors:
        raise click.ClickException(f"Refusing to apply: {len(plan.parse_errors)} parse error(s) in active.md")

    result = apply_archive(plan)
    if output_format != "json":
        click.echo(
            f"Moved {len(result.moved)} task(s); "
            f"{len(result.skipped_duplicates)} duplicate(s) skipped; "
            f"wrote {len(result.destinations_written)} destination file(s)"
        )


@tasks_group.command("edit")
@click.argument("task_id")
@click.option("--title", default=None)
@click.option("--description", default=None)
@click.option("--priority", default=None, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option("--status", default=None)
@click.option("--aspects", "aspects", multiple=True)
@click.option("--related", multiple=True)
@click.option("--blocked-by", multiple=True)
@click.option(
    "--clear-blockers",
    is_flag=True,
    help="Drop all blocked-by refs (e.g. when remediating status drift). Cannot combine with --blocked-by.",
)
@click.option("--group", default=None)
@click.option("--force", is_flag=True, help="Record blockers even if entity not yet known")
def tasks_edit(
    task_id: str,
    title: str | None,
    description: str | None,
    priority: str | None,
    status: str | None,
    aspects: tuple[str, ...],
    related: tuple[str, ...],
    blocked_by: tuple[str, ...],
    clear_blockers: bool,
    group: str | None,
    force: bool,
) -> None:
    """Edit an existing task's fields."""
    from science_tool.tasks import TaskAspectValidationError, edit_task, validate_task_aspects
    from science_tool.tasks_blockers import BlockerValidationError

    if clear_blockers and blocked_by:
        raise click.ClickException("--clear-blockers cannot be combined with --blocked-by")

    validated_aspects: list[str] | None = None
    if aspects:
        try:
            validated_aspects = validate_task_aspects(list(aspects))
        except TaskAspectValidationError as exc:
            raise click.ClickException(str(exc)) from exc

    # None = leave blocked-by untouched; [] = clear it. --clear-blockers forces the
    # empty list so a stale blocker can be dropped without hand-editing active.md.
    blocked_by_arg: list[str] | None
    if clear_blockers:
        blocked_by_arg = []
    elif blocked_by:
        blocked_by_arg = list(blocked_by)
    else:
        blocked_by_arg = None

    try:
        task = edit_task(
            project_root=Path.cwd(),
            tasks_dir=DEFAULT_TASKS_DIR,
            task_id=task_id,
            title=title,
            description=description,
            priority=priority,
            status=status,
            aspects=validated_aspects,
            related=list(related) if related else None,
            blocked_by=blocked_by_arg,
            group=group,
            force=force,
        )
    except BlockerValidationError as e:
        raise click.ClickException(str(e)) from e
    except (KeyError, ValueError) as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Edited [{task.id}] {task.title}")


@tasks_group.command("note")
@click.argument("task_id")
@click.argument("note")
@click.option("--date", "note_date_raw", default=None, help="Note date in YYYY-MM-DD format.")
def tasks_note(task_id: str, note: str, note_date_raw: str | None) -> None:
    """Append a dated note to a task."""
    from datetime import date

    from science_tool.tasks import append_task_note

    note_date = date.today()
    if note_date_raw is not None:
        try:
            note_date = date.fromisoformat(note_date_raw)
        except ValueError as exc:
            raise click.ClickException("Date must use YYYY-MM-DD") from exc

    try:
        task = append_task_note(DEFAULT_TASKS_DIR, task_id, note, note_date=note_date)
    except (KeyError, ValueError) as e:
        raise click.ClickException(str(e)) from e
    click.echo(f"Added note to [{task.id}] ({note_date.isoformat()})")


@tasks_group.command("list")
@click.option("--priority", default=None, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option(
    "--status",
    default=None,
    type=click.Choice(["proposed", "active", "blocked", "deferred", "retired", "done"]),
)
@click.option("--related", default=None)
@click.option("--group", default=None, help="Filter by group (exact match)")
@click.option("--aspect", "aspects", multiple=True, help="Filter by aspect (repeatable)")
@click.option("--all", "show_all", is_flag=True, default=False, help="Include all task statuses")
@click.option("--format", "output_format", default="table", type=click.Choice(OUTPUT_FORMATS))
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def tasks_list(
    priority: str | None,
    status: str | None,
    related: str | None,
    group: str | None,
    aspects: tuple[str, ...],
    show_all: bool,
    output_format: str,
    output_path: Path | None,
) -> None:
    """List tasks. Active and blocked tasks are shown by default; use --all for every status."""
    from science_model.tasks import Task

    from science_tool.budget.invocation import build_complete_via
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.projection import project_rows
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.tasks import list_tasks, parse_tasks_for_cli
    from science_tool.tasks_display import render_tasks_table, sort_tasks
    from science_tool.tasks_readiness import make_project_resolver

    WORKING_SET = ("active", "blocked")

    # Surface legacy-untyped-blocker warnings on stderr.
    _, warnings = parse_tasks_for_cli(DEFAULT_TASKS_DIR / "active.md")
    for w in warnings:
        click.echo(f"WARNING: {w}", err=True)

    matched = list_tasks(
        DEFAULT_TASKS_DIR,
        project_root=Path.cwd(),
        priority=priority,
        status=status,
        related=related,
        group=group,
        aspects=list(aspects) or None,
        include_done=show_all,
    )
    if status is None and not show_all:
        matched = [task for task in matched if task.status in WORKING_SET]
    matched = sort_tasks(matched)

    complete_via = build_complete_via(click.get_current_context(), output_hint="tasks.json")
    control_notice = (
        bounded_control_notice(f"wrote {len(matched)} tasks to {output_path}")
        if output_path is not None
        else None
    )
    sink = BoundedSink(
        lookup("tasks list"),
        output_path=output_path,
        command_path="tasks list",
        complete_via=complete_via,
    )

    try:
        resolver = make_project_resolver()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        columns: list[tuple[str, str]] = [
            ("id", "ID"),
            ("title", "Title"),
            ("type", "Type"),
            ("priority", "Priority"),
            ("status", "Status"),
            ("group", "Group"),
            ("related", "Related"),
            ("created", "Created"),
        ]

        def _row_with_readiness(t: Task) -> dict:
            row: dict = {
                "id": t.id,
                "title": t.title,
                "type": t.type,
                "priority": t.priority,
                "status": t.status,
                "group": t.group,
                "related": ", ".join(t.related),
                "created": t.created.isoformat(),
            }
            if t.status == "blocked" and t.blocked_by:
                readiness_entries = []
                for ref in t.blocked_by:
                    r = resolver.resolve_ref(ref)
                    readiness_entries.append(
                        {
                            "ref": ref,
                            "ready": r.ready,
                            "state": r.state,
                            "detail": r.detail,
                            "unresolved": r.state == "unresolved",
                        }
                    )
                row["blocked_by_readiness"] = readiness_entries
            return row

        rows = [_row_with_readiness(t) for t in matched]
        # Total count of active-file tasks before any filtering, so callers can
        # tell whether they're looking at a curated view or the full list
        # (fb-2026-05-01-006).
        from science_tool.tasks import _read_active

        active_total = len(_read_active(DEFAULT_TASKS_DIR))
        applied_filters: dict[str, object] = {}
        if priority is not None:
            applied_filters["priority"] = priority
        if status is not None:
            applied_filters["status"] = status
        if related is not None:
            applied_filters["related"] = related
        if group is not None:
            applied_filters["group"] = group
        if aspects:
            applied_filters["aspects"] = list(aspects)
        if not show_all and status is None:
            applied_filters["only_status"] = list(WORKING_SET)
        meta = {
            "active_total": active_total,
            "returned_count": len(rows),
            "sort_order": "status_rank,id",
            "applied_filters": applied_filters,
        }
        emit_query_rows(
            output_format=output_format,
            title="Tasks",
            columns=columns,
            rows=rows,
            meta=meta,
            sink=sink,
        )
    else:
        projected = project_rows(matched, sink.max_rows)
        footer = (
            [
                f"showing {len(projected.rows)} of {projected.total} rows",
                f"  complete output:  {complete_via}",
            ]
            if projected.truncated
            else []
        )
        render_tasks_table(projected.rows, resolver=resolver, sink=sink, footer=footer)

    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@tasks_group.command("show")
@click.argument("task_id")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def tasks_show(task_id: str, output_format: str) -> None:
    """Show full details of a task."""
    from science_tool.tasks import find_task_location, render_task
    from science_tool.tasks_readiness import make_project_resolver

    try:
        location = find_task_location(DEFAULT_TASKS_DIR, task_id)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc
    task = location.task
    try:
        resolver = make_project_resolver() if task.blocked_by else None
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    readiness_rows = []
    if resolver is not None:
        for ref in task.blocked_by:
            readiness = resolver.resolve_ref(ref)
            readiness_rows.append(
                {
                    "ref": ref,
                    "state": readiness.state,
                    "ready": readiness.ready,
                    "detail": readiness.detail,
                }
            )

    payload = task.model_dump(mode="json")
    payload["blocked_by_readiness"] = readiness_rows

    def _render() -> None:
        click.echo(render_task(task))

        # Append a resolver-enriched readiness section. render_task() already
        # emitted the raw blocked-by line; suppression would require coupling
        # render_task to a resolver, but render_task is also the on-disk
        # serializer and must stay pure.
        if task.blocked_by:
            click.echo("\nBlocker readiness:")
            for readiness in readiness_rows:
                line = f"  - {readiness['ref']:40s}  {readiness['state']}"
                if readiness["detail"]:
                    line += f"  ({readiness['detail']})"
                click.echo(line)

    emit(output_format=output_format, payload=payload, render_text=_render, sort_keys=True)


@tasks_group.command("summary")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def tasks_summary(output_format: str) -> None:
    """Print summary counts by status, type, priority, and group."""
    from collections import Counter

    from science_tool.tasks import parse_tasks, warn_invalid_statuses

    active = parse_tasks(DEFAULT_TASKS_DIR / "active.md")
    if not active:
        emit(
            output_format=output_format,
            payload={"total": 0, "by_status": {}, "by_type": {}, "by_priority": {}, "by_group": {}},
            render_text=lambda: click.echo("No active tasks."),
        )
        return

    warn_invalid_statuses(active)

    by_status = Counter(t.status for t in active)
    by_type = Counter(t.type for t in active)
    by_priority = Counter(t.priority for t in active)
    by_group = Counter(t.group for t in active if t.group)

    def _render() -> None:
        click.echo(f"Total: {len(active)}")
        click.echo("By status:   " + ", ".join(f"{k}: {v}" for k, v in sorted(by_status.items())))
        click.echo("By type:     " + ", ".join(f"{k}: {v}" for k, v in sorted(by_type.items())))
        click.echo("By priority: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_priority.items())))
        if by_group:
            click.echo("By group:    " + ", ".join(f"{k}: {v}" for k, v in sorted(by_group.items())))

    emit(
        output_format=output_format,
        payload={
            "total": len(active),
            "by_status": dict(sorted(by_status.items())),
            "by_type": dict(sorted(by_type.items())),
            "by_priority": dict(sorted(by_priority.items())),
            "by_group": dict(sorted(by_group.items())),
        },
        render_text=_render,
        sort_keys=True,
    )
