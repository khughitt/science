"""`science boundary` -- declare, generate, and check the VCS storage boundary."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import yaml

from science_tool.boundary.config import BoundaryConfigError
from science_tool.boundary.gitio import tracked_ignored, unmanaged_rules
from science_tool.boundary.init import propose_declaration
from science_tool.boundary.sync import BoundaryDirtyError, has_drift, sync, verify_current_tree

_ROOT_OPTION = click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)


@click.group("boundary")
def boundary_group() -> None:
    """Declared version-control storage boundary."""


@boundary_group.command("check")
@_ROOT_OPTION
def check_command(project_root: Path) -> None:
    """Run the two universal checks. Fast enough for pre-commit.

    It DOES load the declaration -- only for the allowlist, and falling back to
    the built-in default if that fails, so a project with a broken `boundary:`
    block still gets both universal checks. Sharing `unanchored_findings` with
    the validate check is what stops the two drifting: this command previously
    applied neither the sign filter nor the allowlist, so a freshly scaffolded
    project printed six warnings and then declared itself clean.
    """
    from science_tool.validate.checks.boundary import load_boundary_state, unanchored_findings

    hits = tracked_ignored(project_root)
    _cfg, allowed, _error = load_boundary_state(project_root)
    warnings = unanchored_findings(unmanaged_rules(project_root), allowed)
    for rule in warnings:
        click.echo(f"warn  {rule.source}:{rule.line}: unanchored pattern {rule.pattern!r}", err=True)
    if not hits:
        click.echo("vcs-boundary: clean (no tracked file matches an ignore rule)")
        return
    click.echo(f"vcs-boundary: FAIL -- {len(hits)} tracked file(s) match an ignore rule:", err=True)
    for hit in hits[:50]:
        click.echo(f"  {hit.path}  ({hit.source}:{hit.line}: {hit.pattern})", err=True)
    if len(hits) > 50:
        click.echo(f"  ... and {len(hits) - 50} more", err=True)
    sys.exit(1)


@boundary_group.command("sync")
@_ROOT_OPTION
@click.option("--check", "check_only", is_flag=True, help="Report drift; write nothing.")
@click.option("--verify-current-tree", "verify", is_flag=True, help="Diff ignore decisions; restore the original.")
def sync_command(project_root: Path, check_only: bool, verify: bool) -> None:
    """Regenerate the managed .gitignore block from science.yaml."""
    try:
        if check_only:
            if has_drift(project_root):
                click.echo("boundary: managed block is stale; run `science boundary sync`", err=True)
                sys.exit(1)
            click.echo("boundary: managed block is current")
            return
        if verify:
            changes = verify_current_tree(project_root)
            if changes:
                click.echo(f"boundary: {len(changes)} ignore decision(s) would change:", err=True)
                for path, was_ignored, now_ignored in changes:
                    click.echo(f"  {path}: ignored={was_ignored} -> {now_ignored}", err=True)
                sys.exit(1)
            click.echo("boundary: no ignore decision changes")
            return
        result = sync(project_root)
        click.echo("boundary: managed block updated" if result.changed else "boundary: already current")
    except BoundaryDirtyError as exc:
        click.echo(f"boundary: {exc}", err=True)
        sys.exit(2)
    except BoundaryConfigError as exc:
        click.echo(f"boundary: {exc}", err=True)
        sys.exit(2)


@boundary_group.command("init")
@_ROOT_OPTION
def init_command(project_root: Path) -> None:
    """Propose a boundary declaration for review. Writes nothing."""
    proposal = propose_declaration(project_root)
    if not proposal["roots"]:
        click.echo("boundary: no candidate roots found; declare them by hand in science.yaml")
        return
    click.echo("# Proposed for science.yaml -- REVIEW before pasting:")
    click.echo(yaml.safe_dump({"boundary": proposal}, sort_keys=False).rstrip())
    click.echo("\n# Then: science boundary sync --verify-current-tree")
