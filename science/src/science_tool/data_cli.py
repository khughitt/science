from __future__ import annotations

from pathlib import Path

import click

from science_tool.data_audit import Violation, audit_project, audit_project_notes, render_json
from science_tool.data_audit_fix import apply_fixes
from science_tool.data_root import DataRootConfigError
from science_tool.project_config import load_project_config, resolve_data_policy


@click.group("data")
def data_group() -> None:
    """Audit the data/results/entities tracking boundary."""


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _fix_output_overlap(
    project_path: Path,
    output_path: Path,
    violations: list[Violation],
) -> tuple[str, str] | None:
    """Return the first audited path that overlaps the normalized output path."""
    normalized_output = output_path.resolve(strict=False)
    project_root = project_path.resolve()
    for violation in violations:
        source = (project_root / violation.path).resolve(strict=False)
        if _paths_overlap(normalized_output, source):
            return "source", violation.path
        if violation.proposed_target is not None:
            destination = (project_root / violation.proposed_target).resolve(strict=False)
            if _paths_overlap(normalized_output, destination):
                return "proposed destination", violation.proposed_target
    return None


@data_group.command("audit")
@click.option(
    "--project-root",
    "--project",
    "project_path",
    type=click.Path(path_type=Path),
    default=None,
    envvar="SCIENCE_PROJECT_ROOT",
    help="Project root (defaults to $SCIENCE_PROJECT_ROOT or cwd).",
)
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="Relocate stranded records data/ → results/ (stages, never commits). "
    "Requires --output PATH when there are violations to act on.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the machine-readable move report.",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path, file_okay=True, dir_okay=False),
    default=None,
)
def data_audit_command(
    project_path: Path | None,
    fix: bool,
    output_format: str,
    as_json: bool,
    output_path: Path | None,
) -> None:
    """Report (and optionally fix) data/results/entities boundary violations."""
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    emit_json = as_json or output_format == "json"
    project_path = project_path or Path.cwd()  # runtime default; honors the env var above
    try:
        policy = resolve_data_policy(load_project_config(project_path))
    except FileNotFoundError:
        from science_tool.data_policy import DEFAULT_DATA_POLICY

        policy = DEFAULT_DATA_POLICY
    violations = audit_project(project_path, policy)
    try:
        notes = audit_project_notes(project_path)
    except DataRootConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    sink = BoundedSink(
        lookup("data audit"),
        output_path=output_path,
        command_path="data audit",
        complete_via=build_complete_via(
            click.get_current_context(), output_hint=hint_for("audit", output_format)
        ),
    )
    control_notice = (
        bounded_control_notice(f"wrote the data audit report to {output_path}")
        if output_path is not None
        else None
    )

    if fix and violations:
        # The post-fix report is not safely size-bounded before apply_fixes moves files:
        # JSON can add unbounded rewritten-resource details. Require the ceiling-free
        # file sink instead of risking a budget failure after mutation.
        if output_path is None:
            raise click.UsageError(
                f"data audit --fix would act on {len(violations)} violation(s), and the "
                f"size of the resulting report cannot be bounded before the moves run. "
                f"A budget failure after mutating would leave the tree changed with no "
                f"report. Re-run with --output PATH."
            )
        overlap = _fix_output_overlap(project_path, output_path, violations)
        if overlap is not None:
            kind, audited_path = overlap
            raise click.UsageError(
                f"data audit --fix output {output_path} collides with or overlaps audited "
                f"{kind} {audited_path}. Refusing before any file is moved."
            )

    if fix:
        def apply_render_and_flush() -> None:
            outcomes = apply_fixes(project_path, violations)
            if emit_json:
                sink.write(render_json(violations, outcomes, notes))
            else:
                performed = sum(1 for o in outcomes if o.performed)
                flagged = sum(1 for o in outcomes if not o.performed)
                for o in outcomes:
                    mark = "moved" if o.performed else "FLAG"
                    tgt = o.violation.proposed_target or "-"
                    sink.echo(
                        f"  [{mark}] {o.violation.path} → {tgt}"
                        + (f"  ({o.reason})" if o.reason else "")
                    )
                sink.echo(
                    f"\n{performed} moved (staged, not committed), {flagged} flagged."
                )
            sink.flush()

        if violations:
            reserved = False
            try:
                with sink.reserve_output():
                    reserved = True
                    apply_render_and_flush()
            except OSError as exc:
                if not reserved:
                    raise click.UsageError(
                        f"data audit --fix cannot reserve its report destination "
                        f"{output_path}: {exc}. Refusing before any file is moved."
                    ) from exc
                raise
        else:
            apply_render_and_flush()
        if control_notice is not None:
            click.echo(control_notice)
        return

    if emit_json:
        sink.write(render_json(violations, notes=notes))
    else:
        for note in notes:
            sink.echo(f"  [{note.severity}:{note.code}] {note.message}")
        if not violations:
            sink.echo("clean: no data/results boundary violations.")
        for v in violations:
            tgt = v.proposed_target or "-"
            sink.echo(f"  [{v.quadrant.value}] {v.path} → {tgt}")

    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
    if violations:
        raise SystemExit(1)
