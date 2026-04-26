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


@artifacts_group.command("check")
@click.argument("name")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=str),
    default=".",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def check_cmd(name: str, project_root: str, as_json: bool) -> None:
    """Check the installed status of NAME against PROJECT_ROOT."""
    import json as _json
    from pathlib import Path

    from science_tool.project_artifacts.status import classify_full

    registry = default_registry()
    art = next((a for a in registry.artifacts if a.name == name), None)
    if art is None:
        raise click.ClickException(f"no managed artifact named {name!r} in the registry")

    target = Path(project_root) / art.install_target
    result = classify_full(target, art, [])

    if as_json:
        click.echo(
            _json.dumps(
                {
                    "name": art.name,
                    "version": art.version,
                    "install_target": str(target),
                    "status": result.status.value,
                    "detail": result.detail,
                    "versions_behind": result.versions_behind,
                }
            )
        )
    else:
        click.echo(f"{art.name}: {result.status.value}")
        if result.detail:
            click.echo(f"  {result.detail}")


@artifacts_group.command("diff")
@click.argument("name")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=str),
    default=".",
)
def diff_cmd(name: str, project_root: str) -> None:
    """Show unified diff: installed vs canonical for NAME."""
    import difflib
    from pathlib import Path

    from science_tool.project_artifacts.paths import canonical_path

    registry = default_registry()
    art = next((a for a in registry.artifacts if a.name == name), None)
    if art is None:
        raise click.ClickException(f"no managed artifact named {name!r} in the registry")

    target = Path(project_root) / art.install_target
    if not target.exists():
        raise click.ClickException(f"no installed file at {target}")

    canonical = canonical_path(name)
    installed_lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    canonical_lines = canonical.read_text(encoding="utf-8").splitlines(keepends=True)

    diff = difflib.unified_diff(
        canonical_lines,
        installed_lines,
        fromfile=f"canonical/{art.name}",
        tofile=f"installed/{art.name}",
    )
    for line in diff:
        click.echo(line, nl=False)
