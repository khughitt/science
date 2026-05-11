"""Click CLI group for the `annotate` subcommands.

Phase 3.1 ships the `verify` subcommand. Later phases (P3.2+) will add
`audit`, `lift-tokens`, `list`, `ack`, `dismiss`, `fix`, `render`, and
`stats` to this group.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click

from science_tool.annotation.audit import audit_file
from science_tool.annotation.sources import LINT_SOURCES, SOURCES
from science_tool.annotation.verify import (
    VerifyReport,
    apply_supersessions,
    verify_path,
)
from science_tool.output import OUTPUT_FORMATS


@click.group("annotate")
def annotate_group() -> None:
    """Annotation-system tooling (W3C Web Annotation sidecars)."""


@annotate_group.command("verify")
@click.option(
    "--root",
    "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root to walk for *.anno.trig files.",
)
@click.option(
    "--summary-only",
    is_flag=True,
    help="Print only aggregate counts, not per-issue lines.",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Promote degraded/fuzzy warnings to failures (exit 1).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    help="Mutate broken annotations to status='superseded' and rewrite sidecars.",
)
@click.option(
    "--actor",
    type=str,
    default=None,
    help="Required with --apply. Identity recorded as dc:contributor on each mutation.",
)
@click.option(
    "--force-dirty",
    is_flag=True,
    help="Bypass the clean-tree guard when --apply is set.",
)
def verify(
    root_path: Path,
    summary_only: bool,
    strict: bool,
    output_format: str,
    apply_changes: bool,
    actor: str | None,
    force_dirty: bool,
) -> None:
    """Resolve every annotation's selector against its source; report drift.

    Default is dry-run. With --apply, broken annotations are mutated to
    status='superseded' and their sidecars rewritten. --apply requires
    --actor.
    """
    root = root_path.resolve()

    if apply_changes:
        if not actor:
            raise click.ClickException("--apply requires --actor <identity>")
        if not force_dirty:
            dirty = _dirty_anno_files(root)
            if dirty:
                raise click.ClickException(
                    "Refusing to --apply: the following annotation files have "
                    "uncommitted changes:\n  "
                    + "\n  ".join(sorted(d.as_posix() for d in dirty))
                    + "\nCommit or stash, or pass --force-dirty to override."
                )

    report = verify_path(root)

    rewritten_count = 0
    pre_apply_broken = 0
    if apply_changes:
        pre_apply_broken = report.broken
        rewritten = apply_supersessions(
            report,
            actor=actor,
            now=datetime.now(timezone.utc),
        )
        rewritten_count = len(rewritten)
        # Re-run after apply so the table/JSON reflects the post-mutation
        # state. Broken count drops to 0 (or near-zero if a rewrite raced
        # with a concurrent edit); degraded/fuzzy/parse-errors unchanged.
        report = verify_path(root)

    if output_format == "json":
        _emit_json(
            report,
            root=root,
            summary_only=summary_only,
            apply_meta=(
                {
                    "rewritten_sidecars": rewritten_count,
                    "superseded_annotations": pre_apply_broken,
                }
                if apply_changes
                else None
            ),
        )
    else:
        if apply_changes:
            click.echo(
                f"annotate verify --apply: rewrote {rewritten_count} sidecar(s); "
                f"superseded {pre_apply_broken} broken annotation(s)."
            )
        _emit_table(report, summary_only=summary_only)

    # Unified exit policy. Parse errors and post-apply broken rows are
    # always hard failures. Strict additionally promotes degraded/fuzzy/
    # source-missing.
    if report.broken > 0 or report.parse_errors > 0:
        raise click.exceptions.Exit(1)
    if strict and (report.degraded > 0 or report.fuzzy > 0 or report.source_missing > 0):
        raise click.exceptions.Exit(1)


def _emit_table(report: VerifyReport, *, summary_only: bool) -> None:
    if (
        report.broken == 0
        and report.degraded == 0
        and report.fuzzy == 0
        and report.source_missing == 0
        and report.parse_errors == 0
    ):
        click.echo(
            f"annotate verify: all clean "
            f"({report.annotations} annotations across {report.sidecars} sidecars; "
            f"0 broken, 0 degraded, 0 fuzzy)"
        )
        if report.superseded_skipped:
            click.echo(
                f"  ({report.superseded_skipped} already-superseded annotations skipped)"
            )
        return

    click.echo(
        f"annotate verify: {report.broken} broken, "
        f"{report.degraded} degraded, {report.fuzzy} fuzzy, "
        f"{report.source_missing} source-missing, "
        f"{report.parse_errors} parse-errors "
        f"({report.annotations} annotations across {report.sidecars} sidecars)"
    )
    if report.superseded_skipped:
        click.echo(
            f"  ({report.superseded_skipped} already-superseded annotations skipped)"
        )

    if summary_only:
        return

    for issue in report.issues:
        click.echo(
            f"  [{issue.kind}] {issue.sidecar.name} :: {issue.annotation_id}"
        )
        if issue.source:
            click.echo(f"      source: {issue.source}")
        if issue.exact_preview:
            click.echo(f"      exact:  {issue.exact_preview!r}")


def _emit_json(
    report: VerifyReport,
    *,
    root: Path,
    summary_only: bool,
    apply_meta: Optional[dict[str, int]] = None,
) -> None:
    summary = {
        "sidecars": report.sidecars,
        "annotations": report.annotations,
        "broken": report.broken,
        "degraded": report.degraded,
        "fuzzy": report.fuzzy,
        "source_missing": report.source_missing,
        "parse_errors": report.parse_errors,
        "superseded_skipped": report.superseded_skipped,
    }
    payload: dict[str, object] = {"summary": summary}
    if apply_meta is not None:
        payload["apply"] = apply_meta
    if not summary_only:
        payload["issues"] = [
            {
                "sidecar": _relpath(issue.sidecar, root),
                "annotation_id": issue.annotation_id,
                "source": issue.source,
                "kind": issue.kind,
                "exact_preview": issue.exact_preview,
            }
            for issue in report.issues
        ]
    click.echo(json.dumps(payload, indent=2))


def _relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _dirty_anno_files(root: Path) -> list[Path]:
    """Return *.anno.trig files with uncommitted changes under `root`.

    Returns an empty list when `root` is not a git repo (we don't refuse
    to apply in non-git contexts; the guard is a convenience for CI/dev
    workflows, not a hard correctness requirement).
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, FileNotFoundError):
        return []
    if result.returncode != 0:
        return []
    dirty: list[Path] = []
    for line in result.stdout.splitlines():
        # Porcelain format: "XY path" — first two chars are status, then space, then path.
        if len(line) < 4:
            continue
        rel = line[3:].strip()
        if rel.endswith(".anno.trig"):
            dirty.append(Path(rel))
    return dirty


@annotate_group.command("audit")
@click.option(
    "--root", "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--source", "sources_opt",
    multiple=True,
    help=(
        "Source short name (repeatable). Defaults to LINT_SOURCES. "
        "Valid: " + ", ".join(sorted(SOURCES))
    ),
)
@click.option(
    "--no-llm", is_flag=True, default=False,
    help="Skip LLM sources (forward-compat no-op in P3.2).",
)
@click.option("--dry-run", is_flag=True, default=False)
@click.option(
    "--format", "fmt",
    type=click.Choice(("table", "json")), default="table",
)
@click.option("--actor", default="science-annotate-cli")
def audit_cmd(
    root_path: Path,
    sources_opt: tuple[str, ...],
    no_llm: bool,
    dry_run: bool,
    fmt: str,
    actor: str,
) -> None:
    """Run mechanical-audit sources; write planned rows to sidecars."""
    del no_llm  # accepted; P3.2 has no LLM sources to skip
    selected_names = tuple(sources_opt) if sources_opt else LINT_SOURCES
    unknown = [s for s in selected_names if s not in SOURCES]
    if unknown:
        click.echo(f"unknown source(s): {unknown!r}", err=True)
        raise SystemExit(1)
    selected = [SOURCES[s] for s in selected_names]
    full_source_names = sorted({s.name for s in selected})

    root = root_path.resolve()
    md_files = _collect_audit_markdown_files(root)
    now = datetime.now(timezone.utc)

    file_reports: list[dict] = []
    summary = {
        "files_scanned": len(md_files),
        "rows_written": 0,
        "duplicates_skipped": 0,
        "files_with_writes": 0,
        "sources_run": full_source_names,
    }

    for md in md_files:
        sidecar = md.with_suffix(".anno.trig")
        if dry_run:
            planned_per_source = {}
            for src in selected:
                plans = list(src.scan(md))
                planned_per_source[src.short_name] = len(plans)
            file_reports.append({
                "path": str(md.relative_to(root)),
                "rows_planned": planned_per_source,
            })
            continue
        report = audit_file(
            md, sidecar, sources=selected, actor=actor, now=now,
        )
        if report.rows_written or report.duplicates_skipped:
            file_reports.append({
                "path": str(md.relative_to(root)),
                "rows_written": report.written_per_source,
                "duplicates_skipped": report.duplicates_skipped,
            })
        summary["rows_written"] += report.rows_written
        summary["duplicates_skipped"] += report.duplicates_skipped
        if report.rows_written:
            summary["files_with_writes"] += 1

    if fmt == "json":
        click.echo(json.dumps({"summary": summary, "files": file_reports}, indent=2))
    else:
        _emit_audit_table(summary, file_reports, dry_run=dry_run)


def _collect_audit_markdown_files(root: Path) -> list[Path]:
    """Mirror prose_lint._collect_markdown_files but importable here."""
    from science_tool.prose_lint import _collect_markdown_files  # noqa: PLC0415
    return _collect_markdown_files(root)


def _emit_audit_table(
    summary: dict, files: list[dict], *, dry_run: bool,
) -> None:
    if dry_run:
        click.echo(f"audit dry-run over {summary['files_scanned']} file(s):")
    else:
        click.echo(
            f"audit: {summary['rows_written']} row(s) written, "
            f"{summary['duplicates_skipped']} duplicate(s) skipped, "
            f"{summary['files_with_writes']} file(s) modified."
        )
    for entry in files:
        click.echo(f"  {entry['path']}: {entry}")
