"""Click commands for `science-tool project artifacts ...`."""

from __future__ import annotations

import click

from science_tool.project_artifacts import default_registry


@click.group("artifacts")
def artifacts_group() -> None:
    """Manage Science-managed project artifacts (validate.sh and friends)."""


@artifacts_group.command("list")
@click.option("--check", is_flag=True, help="Include current status (requires --project-root).")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=str),
    default=".",
    help="Project root for status check.",
)
def list_cmd(check: bool, project_root: str) -> None:
    """List managed artifacts from the registry.

    With --check, also classify each artifact's status against PROJECT_ROOT.
    """
    registry = default_registry()
    if not registry.artifacts:
        click.echo("No managed artifacts in the registry.")
        return

    for art in registry.artifacts:
        if check:
            from pathlib import Path

            from science_tool.project_artifacts.status import classify_full

            target = Path(project_root) / art.install_target
            res = classify_full(target, art, [])  # pins handled in Task 24
            click.echo(f"{art.name}\t{art.version}\t{res.status.value}\t{res.detail}")
        else:
            click.echo(f"{art.name}\t{art.version}")
