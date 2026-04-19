"""Click CLI group for the ``refs`` subcommands."""

from __future__ import annotations

from pathlib import Path

import click

from science_tool.refs_migrate import (
    apply_rewrites,
    check_git_clean,
    render_diff,
    scan_project,
)


@click.group("refs")
def refs_group() -> None:
    """Reference-integrity tooling for Science projects."""


@refs_group.command("migrate-paper")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Project root to migrate.",
)
@click.option("--apply", is_flag=True, help="Write changes to disk (otherwise dry-run).")  # noqa: A002
@click.option("--force", is_flag=True, help="Bypass the clean-git check when applying.")
@click.option("--verbose", is_flag=True, help="Show the full diff without line cap.")
def migrate_paper(
    project_root: Path, apply: bool, force: bool, verbose: bool  # noqa: A002
) -> None:
    """Migrate legacy ``article:`` entity IDs to canonical ``paper:``."""
    rewrites = scan_project(project_root)
    if not rewrites:
        click.echo("No `article:` references found; project is migrated.")
        return

    if not apply:
        diff = render_diff(rewrites, max_lines=None if verbose else 200)
        click.echo(diff)
        total = sum(r.match_count for r in rewrites)
        click.echo(f"Would rewrite {total} legacy paper references in {len(rewrites)} files.")
        click.echo("Re-run with --apply to write changes.")
        return

    if not force and not check_git_clean(project_root):
        raise click.ClickException(
            "Working tree is not clean. Commit or stash changes first, "
            "or re-run with --force to bypass."
        )

    apply_rewrites(rewrites)
    total = sum(r.match_count for r in rewrites)
    click.echo(
        f"Rewrote {total} legacy paper references in {len(rewrites)} files. "
        "Run `science-tool refs check-refs` to verify."
    )
