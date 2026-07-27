"""`science tasks` command group — research/dev task backlog management."""

from __future__ import annotations

import hashlib
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


def _active_source_hash(tasks_dir: Path) -> str:
    """Hash active task filenames and bytes for an optimistic write recheck."""
    digest = hashlib.sha256()
    for path in sorted((tasks_dir / "active").glob("*.md")):
        for part in (path.name.encode("utf-8"), path.read_bytes()):
            digest.update(len(part).to_bytes(8, byteorder="big"))
            digest.update(part)
    return digest.hexdigest()


@tasks_group.command("blockers")
@click.argument("task_id")
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted report to PATH instead of stdout.",
)
def tasks_blockers(task_id: str, fmt: str, output_path: Path | None) -> None:
    """Show per-blocker readiness for a task."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_rows
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
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

    sink = BoundedSink(
        lookup("tasks blockers"),
        output_path=output_path,
        command_path="tasks blockers",
        complete_via=build_complete_via(click.get_current_context(), output_hint=hint_for("tasks-blockers", fmt)),
    )
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} blockers to {output_path}") if output_path is not None else None
    )

    projected = project_rows(rows, sink.max_rows)
    displayed_rows = projected.rows
    payload: dict[str, object] = {"task_id": task.id, "blockers": displayed_rows}
    if projected.truncated:
        payload["truncation"] = {
            "omitted": projected.omitted,
            "total": projected.total,
            "complete_via": sink.complete_via,
        }

    def _render() -> None:
        sink.echo(f"Blockers for [{task.id}] {task.title}:")
        for row in displayed_rows:
            marker = "✓" if row["ready"] else "·"
            line = f"  {marker} {row['ref']:40s}  {row['state']}"
            if row["detail"]:
                line += f"  ({row['detail']})"
            sink.echo(line)
        if projected.truncated:
            sink.echo(f"showing {len(displayed_rows)} of {projected.total} blockers")
            sink.echo(f"  complete output:  {sink.complete_via}")

    emit(output_format=fmt, payload=payload, render_text=_render, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@tasks_group.command("fix-blockers")
@click.option("--dry-run", is_flag=True, help="List legacy untyped blockers without modifying any files")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
    help="Output format for the --dry-run report. The live retyping sweep always prompts interactively.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="With --dry-run, write the complete, unbudgeted report to PATH instead of stdout.",
)
def tasks_fix_blockers(dry_run: bool, output_format: str, output_path: Path | None) -> None:
    """Interactive sweep to retype legacy untyped blockers.

    ``--dry-run`` is a bounded report (bounded stdout, ``--output`` escape). The live
    retyping sweep prompts interactively per blocker and cannot be buffered without
    hiding each prompt from the person it is asking -- so ``--format``/``--output``
    are refused without ``--dry-run``.
    """
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_rows
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.tasks import (
        _read_active,
        _require_split,
        _task_allocation_lock,
        find_task_location,
        write_task_file,
    )
    from science_tool.tasks_blockers import is_typed_ref

    if not dry_run and (output_path is not None or output_format != "table"):
        raise click.UsageError("--format/--output require --dry-run (the live sweep prompts interactively)")

    sink = BoundedSink(
        lookup("tasks fix-blockers"),
        output_path=output_path,
        command_path="tasks fix-blockers",
        complete_via=build_complete_via(
            click.get_current_context(), output_hint=hint_for("tasks-fix-blockers", output_format)
        ),
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete legacy-blocker report to {output_path}")
        if output_path is not None
        else None
    )

    source_hash = _active_source_hash(DEFAULT_TASKS_DIR)
    tasks_ = _read_active(DEFAULT_TASKS_DIR)
    warnings = [
        f"task {task.id}: legacy untyped blocker {ref!r} — run 'science tasks fix-blockers' to retype"
        for task in tasks_
        for ref in task.blocked_by
        if not is_typed_ref(ref)
    ]

    if not warnings or dry_run:
        projected = project_rows(warnings, sink.max_rows)
        displayed = projected.rows
        payload: dict[str, object] = {"legacy_blockers": displayed}
        if projected.truncated:
            payload["truncation"] = {
                "omitted": projected.omitted,
                "total": projected.total,
                "complete_via": sink.complete_via,
            }

        def _render() -> None:
            if not warnings:
                sink.echo("No legacy untyped blockers found.")
                return
            sink.echo("Legacy untyped blockers (dry-run):")
            for w in displayed:
                sink.echo(f"  {w}")
            if projected.truncated:
                sink.echo(f"showing {len(displayed)} of {projected.total} legacy blocker(s)")
                sink.echo(f"  complete output:  {sink.complete_via}")

        emit(output_format=output_format, payload=payload, render_text=_render, sink=sink)
        sink.flush()
        if control_notice is not None:
            click.echo(control_notice)
        return

    changed_tasks = []
    for task in tasks_:
        original_blockers = task.blocked_by
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
                pass  # drop
            else:
                if not is_typed_ref(replacement):
                    click.echo(f"  ! {replacement!r} not a typed ref; keeping original")
                    new_blockers.append(ref)
                else:
                    new_blockers.append(replacement)
        task.blocked_by = new_blockers
        if new_blockers != original_blockers:
            changed_tasks.append(task)

    if changed_tasks and click.confirm("\nWrite changes to active task files?", default=True):
        with _task_allocation_lock(DEFAULT_TASKS_DIR):
            _require_split(DEFAULT_TASKS_DIR)
            _read_active(DEFAULT_TASKS_DIR, require_split=False)
            if _active_source_hash(DEFAULT_TASKS_DIR) != source_hash:
                raise click.ClickException("tasks changed under you; re-run fix-blockers")

            try:
                for task in changed_tasks:
                    location = find_task_location(
                        DEFAULT_TASKS_DIR,
                        task.id,
                        require_split=False,
                    )
                    if location.path.parent != DEFAULT_TASKS_DIR / "active":
                        raise ValueError(
                            f"task {task.id} is no longer an active task; "
                            "re-run fix-blockers"
                        )
            except (KeyError, ValueError) as exc:
                raise click.ClickException(str(exc)) from exc

            for task in changed_tasks:
                write_task_file(DEFAULT_TASKS_DIR, task)
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


@tasks_group.command("migrate-storage")
@click.option("--apply", "do_apply", is_flag=True, help="Apply the migration (default is dry-run).")
@click.option("--resume", "do_resume", is_flag=True, help="Resume an interrupted migration from its journal.")
@click.option(
    "--tasks-dir",
    default=DEFAULT_TASKS_DIR,
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted migration plan to PATH.",
)
def tasks_migrate_storage(
    do_apply: bool,
    do_resume: bool,
    tasks_dir: Path,
    output_format: str,
    output_path: Path | None,
) -> None:
    """Plan, apply, or resume the transactional split-storage migration."""
    from contextlib import nullcontext
    from datetime import date

    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.tasks import _tasks_storage_state
    from science_tool.tasks_migrate import (
        MigrationPlan,
        MigrationRefused,
        apply_migration,
        migration_mode_refusal,
        plan_migration,
        resume_migration,
    )

    if do_apply and do_resume:
        raise click.UsageError("--apply and --resume are mutually exclusive")

    if output_path is not None:
        tasks_root = tasks_dir.resolve()
        resolved_output = output_path.resolve()
        protected_files = {
            tasks_root / "active.md",
            tasks_root / ".tasks.lock",
            tasks_root / ".science" / "task-storage-migration.journal",
        }
        protected_directories = (tasks_root / "active", tasks_root / "done")
        if resolved_output in protected_files or any(
            resolved_output.is_relative_to(directory)
            for directory in protected_directories
        ):
            raise click.UsageError(
                "--output overlaps transaction-owned task storage; choose a path "
                "outside active.md, active/, done/, the journal, and .tasks.lock"
            )

    sink = BoundedSink(
        lookup("tasks migrate-storage"),
        output_path=output_path,
        command_path="tasks migrate-storage",
        complete_via=build_complete_via(
            click.get_current_context(),
            output_hint=hint_for("tasks-migrate-storage", output_format),
        ),
    )

    def _plan_rows(plan: MigrationPlan) -> list[dict[str, str]]:
        return [
            {
                "id": entry.task.id,
                "status": entry.task.status,
                "destination": entry.destination.as_posix() if entry.destination is not None else "",
                "action": entry.action,
            }
            for entry in plan.entries
        ]

    def _emit_rows(
        rows: list[dict[str, str]],
        *,
        title: str,
        mode: str,
        summary: str,
        source_count: int | None = None,
    ) -> None:
        emit_query_rows(
            output_format=output_format,
            title=title,
            columns=[
                ("id", "ID"),
                ("status", "Status"),
                ("destination", "Destination"),
                ("action", "Action"),
            ],
            rows=rows,
            meta={
                "mode": mode,
                "source_count": len(rows) if source_count is None else source_count,
            },
            sink=sink,
        )
        if output_format != "json":
            sink.echo(summary)

    def _flush_with_notice(row_count: int, *, noun: str) -> None:
        sink.flush()
        if output_path is not None:
            click.echo(
                bounded_control_notice(f"wrote {row_count} {noun} rows to {output_path}")
            )

    def _emit_mutation_summary(
        *,
        mode: str,
        source_count: int,
        written_count: int,
        summary: str,
    ) -> None:
        emit(
            output_format=output_format,
            payload={
                "format": "json",
                "mode": mode,
                "source_count": source_count,
                "written_count": written_count,
            },
            render_text=lambda: sink.echo(summary),
            sink=sink,
        )

    def _exit_with_refusal(exc: MigrationRefused, *, mode: str) -> None:
        reasons = [line.strip() for line in str(exc).splitlines() if line.strip()]
        rows = [
            {
                "id": "",
                "status": "refusal",
                "destination": "",
                "action": reason,
            }
            for reason in reasons
        ]
        _emit_rows(
            rows,
            title="Task Storage Migration Refused",
            mode=mode,
            summary=f"Migration refused during {mode}; nothing further was written.",
            source_count=0,
        )
        _flush_with_notice(len(rows), noun="migration-refusal")
        click.get_current_context().exit(1)

    if do_resume:
        state_refusal = migration_mode_refusal(_tasks_storage_state(tasks_dir), "resume")
        if state_refusal is not None:
            raise click.ClickException(state_refusal)
        try:
            reservation = sink.reserve_output() if sink.is_file_sink else nullcontext()
            with reservation:
                result = resume_migration(tasks_dir)
                summary = (
                    "Resumed storage migration; "
                    f"wrote {len(result.written)} missing post-image(s), "
                    f"verified {len(result.entries)} total."
                )
                if sink.is_file_sink:
                    rows = [
                        {
                            "id": "",
                            "status": "",
                            "destination": entry.destination.as_posix(),
                            "action": entry.action,
                        }
                        for entry in result.entries
                    ]
                    _emit_rows(
                        rows,
                        title="Task Storage Migration Resume",
                        mode="resumed",
                        summary=summary,
                    )
                    _flush_with_notice(len(rows), noun="migration-resume")
                else:
                    _emit_mutation_summary(
                        mode="resumed",
                        source_count=len(result.entries),
                        written_count=len(result.written),
                        summary=summary,
                    )
                    _flush_with_notice(0, noun="migration-resume")
        except MigrationRefused as exc:
            _exit_with_refusal(exc, mode="resume")
        return

    if do_apply:
        state_refusal = migration_mode_refusal(_tasks_storage_state(tasks_dir), "apply")
        if state_refusal is not None:
            raise click.ClickException(state_refusal)
        try:
            reservation = sink.reserve_output() if sink.is_file_sink else nullcontext()
            with reservation:
                plan = apply_migration(tasks_dir, today=date.today())
                rows = _plan_rows(plan)
                summary = f"Migrated {len(rows)} task(s)."
                if sink.is_file_sink:
                    _emit_rows(
                        rows,
                        title="Task Storage Migration Applied",
                        mode="applied",
                        summary=summary,
                    )
                    _flush_with_notice(len(rows), noun="migration-plan")
                else:
                    _emit_mutation_summary(
                        mode="applied",
                        source_count=len(rows),
                        written_count=len(plan.post_images),
                        summary=summary,
                    )
                    _flush_with_notice(0, noun="migration-plan")
        except MigrationRefused as exc:
            _exit_with_refusal(exc, mode="apply")
        return

    plan = plan_migration(tasks_dir, today=date.today())
    if plan.refusals:
        rows = [
            {
                "id": "",
                "status": "refusal",
                "destination": "",
                "action": reason,
            }
            for reason in plan.refusals
        ]
        rows.extend(_plan_rows(plan))
        _emit_rows(
            rows,
            title="Task Storage Migration Refused",
            mode="refused",
            summary=(
                "Mode: dry-run — migration refused; "
                f"{len(plan.refusals)} issue(s), nothing written."
            ),
            source_count=len(plan.entries),
        )
        _flush_with_notice(len(rows), noun="migration-plan")
        click.get_current_context().exit(1)
    rows = _plan_rows(plan)
    _emit_rows(
        rows,
        title="Task Storage Migration Plan",
        mode="dry-run",
        summary=f"Mode: dry-run — would migrate {len(rows)} task(s).",
    )
    _flush_with_notice(len(rows), noun="migration-plan")


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
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def tasks_archive(do_apply: bool, check: bool, output_format: str, tasks_dir: Path, output_path: Path | None) -> None:
    """Move done/retired tasks from active.md to done/YYYY-MM.md.

    Default is dry-run: prints the planned moves without touching disk.
    Pass --apply to perform the writes (idempotent on re-run).
    """
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
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

    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("tasks-archive", output_format))
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("tasks archive"), output_path=output_path, command_path="tasks archive", complete_via=complete_via
    )
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
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)

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
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    default=False,
    help="Include all statuses in the active store (does not read done ledgers)",
)
@click.option(
    "--since",
    "since_raw",
    default=None,
    help="Only show tasks closed on or after this date (YYYY-MM-DD). Requires closed statuses.",
)
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
    since_raw: str | None,
    output_format: str,
    output_path: Path | None,
) -> None:
    """List tasks from the active store; use --since for bounded closed-task reads."""
    from datetime import date

    from science_model.tasks import Task

    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.projection import project_rows
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.tasks import _CLOSED_STATUS_VALUES, list_tasks, parse_tasks_for_cli
    from science_tool.tasks_display import render_tasks_table, sort_tasks
    from science_tool.tasks_readiness import make_project_resolver

    WORKING_SET = ("active", "blocked")

    since: date | None = None
    if since_raw is not None:
        try:
            since = date.fromisoformat(since_raw)
        except ValueError as exc:
            raise click.ClickException("Date must use YYYY-MM-DD") from exc
        if status is not None and status not in _CLOSED_STATUS_VALUES:
            raise click.UsageError(
                "--since only applies to closed tasks; use --status done, --status retired, or --all"
            )
    elif status in _CLOSED_STATUS_VALUES:
        raise click.UsageError(
            f"--status {status} requires --since YYYY-MM-DD to bound done-ledger reads"
        )

    try:
        matched = list_tasks(
            DEFAULT_TASKS_DIR,
            project_root=Path.cwd(),
            priority=priority,
            status=status,
            related=related,
            group=group,
            aspects=list(aspects) or None,
            include_done=show_all,
            since=since,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    # Surface legacy-untyped-blocker warnings on stderr.
    _, warnings = parse_tasks_for_cli(DEFAULT_TASKS_DIR, require_split=False)
    for w in warnings:
        click.echo(f"WARNING: {w}", err=True)

    if status is None and not show_all and since is None:
        matched = [task for task in matched if task.status in WORKING_SET]
    matched = sort_tasks(matched)

    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("tasks", output_format))
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
        # Total count of active tasks before any filtering, so callers can
        # tell whether they're looking at a curated view or the full list
        # (fb-2026-05-01-006).
        from science_tool.tasks import _read_active

        active_total = len(_read_active(DEFAULT_TASKS_DIR, require_split=False))
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
        if not show_all and status is None and since is None:
            applied_filters["only_status"] = list(WORKING_SET)
        meta = {
            "returned_count": len(rows),
            "sort_order": "status_rank,id",
            "applied_filters": applied_filters,
        }
        # active_total counts only tasks/active/ and is meaningless for a
        # --since query, whose rows come from the archive union — omit it
        # rather than ship a "curated vs full" ratio that doesn't apply.
        if since is None:
            meta["active_total"] = active_total
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
    except (KeyError, ValueError) as exc:
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
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted summary to PATH instead of stdout.",
)
def tasks_summary(output_format: str, output_path: Path | None) -> None:
    """Print summary counts by status, type, priority, and group."""
    from collections import Counter

    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.tasks import _read_active, warn_invalid_statuses
    from science_tool.tasks_summary_projection import project_tasks_summary

    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("tasks-summary", output_format))
    sink = BoundedSink(
        lookup("tasks summary"), output_path=output_path, command_path="tasks summary", complete_via=complete_via
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete task summary to {output_path}")
        if output_path is not None
        else None
    )

    try:
        active = _read_active(DEFAULT_TASKS_DIR)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if not active:
        full = {"total": 0, "by_status": {}, "by_type": {}, "by_priority": {}, "by_group": {}}
        emit(output_format=output_format, payload=full, render_text=lambda: sink.echo("No active tasks."), sink=sink)
        sink.flush()
        if control_notice is not None:
            click.echo(control_notice)
        return

    warn_invalid_statuses(active)

    by_status = Counter(t.status for t in active)
    by_type = Counter(t.type for t in active)
    by_priority = Counter(t.priority for t in active)
    by_group = Counter(t.group for t in active if t.group)

    full = {
        "total": len(active),
        "by_status": dict(sorted(by_status.items())),
        "by_type": dict(sorted(by_type.items())),
        "by_priority": dict(sorted(by_priority.items())),
        "by_group": dict(sorted(by_group.items())),
    }
    displayed = full if output_path is not None else project_tasks_summary(full)

    def _render() -> None:
        sink.echo(f"Total: {displayed['total']}")
        sink.echo("By status:   " + ", ".join(f"{k}: {v}" for k, v in displayed["by_status"].items()))
        sink.echo("By type:     " + ", ".join(f"{k}: {v}" for k, v in displayed["by_type"].items()))
        sink.echo("By priority: " + ", ".join(f"{k}: {v}" for k, v in displayed["by_priority"].items()))
        if displayed["by_group"]:
            sink.echo("By group:    " + ", ".join(f"{k}: {v}" for k, v in displayed["by_group"].items()))
        omitted = {
            key: displayed[f"{key}_omitted"]
            for key in ("by_status", "by_type", "by_priority", "by_group")
            if displayed.get(f"{key}_omitted", 0)
        }
        if omitted:
            sink.echo(f"omitted: {omitted}")
            sink.echo(f"  complete output:  {complete_via}")

    emit(output_format=output_format, payload=displayed, render_text=_render, sink=sink, sort_keys=True)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
