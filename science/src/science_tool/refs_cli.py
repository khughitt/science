"""Click CLI group for the ``refs`` subcommands."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TypedDict

import click

from science_tool.output import OUTPUT_FORMATS
from science_tool.peers import PeerUnresolved
from science_tool.refs import RefIssue, check_refs
from science_tool.refs_migrate import (
    apply_rewrites,
    check_git_clean,
    render_diff,
    scan_project,
)


@click.group("refs")
def refs_group() -> None:
    """Reference-integrity tooling for Science projects."""


class RefsSummary(TypedDict):
    broken: int
    markers: int
    by_type: dict[str, int]


def _refs_summary(broken: list[RefIssue], markers: list[RefIssue]) -> RefsSummary:
    return {
        "broken": len(broken),
        "markers": len(markers),
        "by_type": dict(sorted(Counter(issue.ref_type for issue in broken).items())),
    }


def _render_marker_summary(markers: list[RefIssue], *, include_locations: bool) -> None:
    unverified = [m for m in markers if m.ref_value == "[UNVERIFIED]"]
    needs_cite = [m for m in markers if m.ref_value == "[NEEDS CITATION]"]
    click.echo("  Unresolved markers:")
    if unverified:
        if include_locations:
            locs = ", ".join(f"{m.file}:{m.line}" for m in unverified)
            click.echo(f"    {len(unverified)}x [UNVERIFIED] ({locs})")
        else:
            click.echo(f"    {len(unverified)}x [UNVERIFIED]")
    if needs_cite:
        if include_locations:
            locs = ", ".join(f"{m.file}:{m.line}" for m in needs_cite)
            click.echo(f"    {len(needs_cite)}x [NEEDS CITATION] ({locs})")
        else:
            click.echo(f"    {len(needs_cite)}x [NEEDS CITATION]")


@refs_group.command("check")
@click.option("--root", "root_path", default=".", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option("--strict", is_flag=True, help="Exit with error on any broken ref (not just markers)")
@click.option("--summary-only", is_flag=True, help="Print only aggregate counts, not individual references.")
def check(root_path: Path, output_format: str, strict: bool, summary_only: bool) -> None:
    """Scan project documents for broken cross-references."""

    try:
        issues = check_refs(root_path.resolve())
    except PeerUnresolved as exc:
        raise click.ClickException(str(exc)) from exc

    broken = [i for i in issues if i.ref_type != "marker"]
    markers = [i for i in issues if i.ref_type == "marker"]
    summary = _refs_summary(broken, markers)

    if output_format == "json":
        import json

        payload: dict[str, object] = {"summary": summary}
        if not summary_only:
            payload.update(
                {
                    "broken": [
                        {
                            "file": i.file,
                            "line": i.line,
                            "type": i.ref_type,
                            "value": i.ref_value,
                            "message": i.message,
                            "suggestion": i.suggestion,
                        }
                        for i in broken
                    ],
                    "markers": [{"file": i.file, "line": i.line, "value": i.ref_value} for i in markers],
                }
            )
        click.echo(
            json.dumps(
                payload,
                indent=2,
            )
        )
    else:
        if broken:
            click.echo(f"refs check: {len(broken)} broken, {len(markers)} unresolved markers\n")
            click.echo("By type:")
            for ref_type, count in summary["by_type"].items():
                click.echo(f"  {ref_type}: {count}")
            click.echo()
            if not summary_only:
                for issue in broken:
                    click.echo(f"  {issue.file}:{issue.line}")
                    click.echo(f"    {issue.message}")
                    if issue.suggestion:
                        click.echo(f"    Suggestion: {issue.suggestion}")
                    click.echo()
        elif markers:
            click.echo(f"refs check: 0 broken, {len(markers)} unresolved markers\n")
        else:
            click.echo("refs check: all references valid, no unresolved markers")
            return

        if markers:
            _render_marker_summary(markers, include_locations=not summary_only)

    if broken:
        raise click.exceptions.Exit(1)
    if strict and markers:
        raise click.exceptions.Exit(1)


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
    project_root: Path,
    apply: bool,
    force: bool,
    verbose: bool,  # noqa: A002
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
            "Working tree is not clean. Commit or stash changes first, or re-run with --force to bypass."
        )

    apply_rewrites(rewrites)
    total = sum(r.match_count for r in rewrites)
    click.echo(
        f"Rewrote {total} legacy paper references in {len(rewrites)} files. "
        "Run `science refs check --root <project-root>` to verify."
    )
