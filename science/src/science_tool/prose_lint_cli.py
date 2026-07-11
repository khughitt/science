"""CLI for `science prose lint`. See docs/conventions/prose-lints.md."""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

import click

from science_tool.bibliography import load_bib_author_surnames
from science_tool.data_root import project_config_path
from science_tool.output import emit
from science_tool.project_config import DEFAULT_ANCHOR_PATTERNS, load_project_config
from science_tool.prose_lint import CHECKS, build_short_form_resolver, scan_root


@click.group("prose")
def prose_group() -> None:
    """Prose-quality lints (bare author-year, short-form IDs, etc.)."""


@prose_group.command("lint")
@click.option("--root", type=click.Path(exists=True, file_okay=False, path_type=Path), default=Path("."))
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table")
@click.option(
    "--check",
    "checks",
    type=click.Choice(list(CHECKS)),
    multiple=True,
    help="Run only the named check(s). Defaults to all.",
)
@click.option("--strict", is_flag=True, help="Promote info-severity issues to warn; exit non-zero on any issue.")
def lint_cmd(root: Path, fmt: str, checks: tuple[str, ...], strict: bool) -> None:
    """Run prose-quality lints across the project's doc/ and entities/ trees."""
    selected = list(checks) if checks else None
    anchor_patterns = list(DEFAULT_ANCHOR_PATTERNS)
    enabled_from_config: list[str] | None = None
    exclude_paths: list[str] = []
    short_form_ids_deny: list[str] = []
    bare_author_year_deny: list[str] = []
    science_yaml = project_config_path(root)
    if science_yaml.is_file():
        config = load_project_config(root)
        if config.prose_lint is not None:
            anchor_patterns = config.prose_lint.anchor_patterns
            enabled_from_config = config.prose_lint.enabled_checks
            exclude_paths = config.prose_lint.exclude_paths
            short_form_ids_deny = config.prose_lint.short_form_ids_deny
            bare_author_year_deny = config.prose_lint.bare_author_year_deny
    if selected is None and enabled_from_config:
        selected = enabled_from_config

    effective_checks = selected if selected is not None else list(CHECKS)
    resolver = (
        build_short_form_resolver(root) if "short-form-ids" in effective_checks else None
    )
    bib_surnames = (
        load_bib_author_surnames(root) if "bare-author-year" in effective_checks else None
    )

    result = scan_root(
        root,
        checks=selected,
        strict=strict,
        anchor_patterns=anchor_patterns,
        exclude_paths=exclude_paths,
        short_form_ids_deny=short_form_ids_deny,
        resolver=resolver,
        bare_author_year_deny=bare_author_year_deny,
        bib_surnames=bib_surnames,
    )

    payload = {
        "counts": result["counts"],
        "hits": [
            {**asdict(h), "file": str(h.file.relative_to(root))}
            for h in result["hits"]
        ],
    }

    emit(output_format=fmt, payload=payload, render_text=lambda: _render_table(result, root))

    # Mirrors `science markers scan`: only --strict + issues fails the run.
    if strict and result["hits"]:
        sys.exit(1)


def _render_table(result: dict, root: Path) -> None:
    if not result["hits"]:
        click.echo("prose lint: no issues found.")
        return
    by_file: dict[Path, list] = {}
    for hit in result["hits"]:
        by_file.setdefault(hit.file, []).append(hit)
    for path in sorted(by_file):
        rel = path.relative_to(root)
        click.echo(f"\n{rel}")
        for hit in sorted(by_file[path], key=lambda h: (h.line, h.col)):
            tag = f"({hit.severity})"
            click.echo(f"  {hit.line}:{hit.col} [{hit.check}] {tag} {hit.message}")
    click.echo("\nSummary:")
    for check, count in sorted(result["counts"].items()):
        click.echo(f"  {check}: {count}")
