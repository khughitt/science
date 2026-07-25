"""`science autonomy` -- the supervisor-facing surface of the autonomy envelope."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from science_model.autonomous_runs import RunTier

from science_tool.output import OUTPUT_FORMATS, emit


@click.group("autonomy")
def autonomy_group() -> None:
    """Evaluate what an autonomous run was permitted to write."""


@autonomy_group.command("path-gate")
@click.option("--base", required=True, help="Commit the run started from (the recorded baseline).")
@click.option("--head", required=True, help="Commit the run ended at.")
@click.option(
    "--tier",
    type=click.Choice([tier.value for tier in RunTier]),
    default=RunTier.BELIEF_NEUTRAL.value,
    show_default=True,
    help="Tier the run was attested to (design §1).",
)
@click.option(
    "--report-path",
    default=None,
    help="Repository-relative path of the run's own report -- the only path 'report-only' may write.",
)
@click.option(
    "--project-root",
    type=click.Path(path_type=Path),
    default=Path("."),
    show_default=True,
    help="Repository root the range is read from.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit the verdict as JSON.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
def path_gate_command(
    base: str,
    head: str,
    tier: str,
    report_path: str | None,
    project_root: Path,
    as_json: bool,
    output_format: str,
) -> None:
    """Decide whether a base..head range stayed inside the tier's write surface.

    Exit codes: 0 allowed, 1 denied, 2 could not evaluate. Exit 2 is explicitly NOT
    allowed -- a gate that cannot see must not report clean (design §5).
    """
    from science_tool.autonomy.extract import ExtractError, extract_change_set
    from science_tool.autonomy.path_gate import GateInputError, evaluate

    effective_format = "json" if as_json else output_format
    try:
        change_set = extract_change_set(project_root, base, head)
        verdict = evaluate(change_set, tier=RunTier(tier), report_path=report_path)
    except (ExtractError, GateInputError) as exc:
        message = f"could not evaluate: {exc}"
        emit(
            output_format=effective_format,
            payload={"allowed": False, "denials": [], "error": message},
            render_text=lambda: click.echo(message),
        )
        sys.exit(2)

    def _render_text() -> None:
        if verdict.allowed:
            click.echo(f"allowed: {len(change_set.changes)} change(s) within tier {tier!r}")
            return
        for denial in verdict.denials:
            location = denial.path if denial.field is None else f"{denial.path} field {denial.field!r}"
            click.echo(f"denied: {location} -- {denial.reason}")

    emit(
        output_format=effective_format,
        payload=verdict.model_dump(mode="json"),
        render_text=_render_text,
    )

    sys.exit(0 if verdict.allowed else 1)
