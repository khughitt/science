"""`science autonomy` -- the supervisor-facing surface of the autonomy envelope."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from science_model.autonomous_runs import RunTier


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
@click.option("--json", "as_json", is_flag=True, help="Emit the verdict as JSON.")
def path_gate_command(
    base: str, head: str, tier: str, report_path: str | None, project_root: Path, as_json: bool
) -> None:
    """Decide whether a base..head range stayed inside the tier's write surface.

    Exit codes: 0 allowed, 1 denied, 2 could not evaluate. Exit 2 is explicitly NOT
    allowed -- a gate that cannot see must not report clean (design §5).
    """
    from science_tool.autonomy.extract import ExtractError, extract_change_set
    from science_tool.autonomy.path_gate import GateInputError, evaluate

    try:
        change_set = extract_change_set(project_root, base, head)
        verdict = evaluate(change_set, tier=RunTier(tier), report_path=report_path)
    except (ExtractError, GateInputError) as exc:
        message = f"could not evaluate: {exc}"
        if as_json:
            click.echo(json.dumps({"allowed": False, "denials": [], "error": message}))
        else:
            click.echo(message)
        sys.exit(2)

    if as_json:
        click.echo(verdict.model_dump_json(indent=2))
    elif verdict.allowed:
        click.echo(f"allowed: {len(change_set.changes)} change(s) within tier {tier!r}")
    else:
        for denial in verdict.denials:
            location = denial.path if denial.field is None else f"{denial.path} field {denial.field!r}"
            click.echo(f"denied: {location} -- {denial.reason}")

    sys.exit(0 if verdict.allowed else 1)
