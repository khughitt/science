"""CLI for `science prose lint`. See docs/conventions/prose-lints.md."""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

import click

from science_tool.bibliography import load_bib_author_surnames
from science_tool.data_root import project_config_path
from science_tool.output import emit
from science_tool.project_config import (
    DEFAULT_ANCHOR_PATTERNS,
    DEFAULT_PROVENANCE_FIELDS,
    DEFAULT_SPEC_CLASS_KINDS,
    ProseLintConfig,
    load_project_config,
)
from science_tool.prose_lint import CHECKS, build_short_form_resolver, couple_checks, merge_anchor_patterns, scan_root


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
    additional_anchor_patterns: list[str] = []
    spec_class_kinds = list(DEFAULT_SPEC_CLASS_KINDS)
    provenance_fields = list(DEFAULT_PROVENANCE_FIELDS)
    enabled_from_config: list[str] | None = None
    exclude_paths: list[str] = []
    short_form_ids_deny: list[str] = []
    bare_author_year_deny: list[str] = []
    prose_lint_config: ProseLintConfig | None = None
    science_yaml = project_config_path(root)
    if science_yaml.is_file():
        config = load_project_config(root)
        if config.prose_lint is not None:
            prose_lint_config = config.prose_lint
            anchor_patterns = prose_lint_config.anchor_patterns
            additional_anchor_patterns = prose_lint_config.additional_anchor_patterns
            spec_class_kinds = prose_lint_config.spec_class_kinds
            provenance_fields = prose_lint_config.provenance_fields
            enabled_from_config = prose_lint_config.enabled_checks
            exclude_paths = prose_lint_config.exclude_paths
            short_form_ids_deny = prose_lint_config.short_form_ids_deny
            bare_author_year_deny = prose_lint_config.bare_author_year_deny
    if prose_lint_config is None:
        # No science.yaml / no `prose_lint:` section: fall back to the same
        # `ProseLintConfig` defaults a configured project would get, rather
        # than letting the CLI's own notion of "default" silently diverge.
        prose_lint_config = ProseLintConfig()
    if selected is None and enabled_from_config:
        selected = enabled_from_config
    if selected is not None:
        selected = couple_checks(selected)
    effective_anchor_patterns = merge_anchor_patterns(anchor_patterns, additional_anchor_patterns)

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
        anchor_patterns=effective_anchor_patterns,
        spec_class_kinds=spec_class_kinds,
        provenance_fields=provenance_fields,
        exclude_paths=exclude_paths,
        short_form_ids_deny=short_form_ids_deny,
        resolver=resolver,
        bare_author_year_deny=bare_author_year_deny,
        bib_surnames=bib_surnames,
        max_json_bytes=prose_lint_config.max_json_bytes,
        max_feather_bytes=prose_lint_config.max_feather_bytes,
    )

    payload = {
        "counts": result["counts"],
        "hits": [
            {**asdict(h), "file": str(h.file.relative_to(root))}
            for h in result["hits"]
        ],
        "coverage": result.get("coverage", {}),
    }

    emit(output_format=fmt, payload=payload, render_text=lambda: _render_table(result, root))

    # Mirrors `science markers scan`: only --strict + issues fails the run.
    if strict and result["hits"]:
        sys.exit(1)


def _render_table(result: dict, root: Path) -> None:
    hits = result["hits"]
    numeric_coverage = (result.get("coverage") or {}).get("numeric-verification")
    if numeric_coverage:
        click.echo(
            "numeric-verification: "
            f"{numeric_coverage.get('verified', 0)} verified, "
            f"{numeric_coverage.get('unverifiable', 0)} unverifiable, "
            f"{numeric_coverage.get('mismatch', 0)} mismatch, "
            f"{numeric_coverage.get('error', 0)} error"
        )
    if not hits:
        if not numeric_coverage:
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
