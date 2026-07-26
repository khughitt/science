"""Click CLI group for the ``refs`` subcommands."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

import click

from science_tool.output import OUTPUT_FORMATS, emit
from science_tool.peers import PeerUnresolved
from science_tool.refs import RefIssue, check_refs


@click.group("refs")
def refs_group() -> None:
    """Reference-integrity tooling for Science projects."""


class RefsSummary(TypedDict):
    broken: int
    markers: int
    by_type: dict[str, int]
    by_value: dict[str, int]


def _refs_summary(broken: list[RefIssue], markers: list[RefIssue], *, by_value: bool) -> RefsSummary:
    summary: RefsSummary = {
        "broken": len(broken),
        "markers": len(markers),
        "by_type": dict(sorted(Counter(issue.ref_type for issue in broken).items())),
        "by_value": {},
    }
    if by_value:
        summary["by_value"] = dict(
            sorted(Counter(f"{issue.ref_type}:{issue.ref_value}" for issue in broken).items())
        )
    return summary


def _filter_issues_by_type(issues: list[RefIssue], ref_types: tuple[str, ...]) -> list[RefIssue]:
    if not ref_types:
        return issues
    requested = set(ref_types)
    return [issue for issue in issues if issue.ref_type in requested]


def _render_marker_summary(markers: list[RefIssue], *, include_locations: bool, echo: Callable[[str], None]) -> None:
    by_token: dict[str, list[RefIssue]] = {}
    for m in markers:
        by_token.setdefault(m.ref_value, []).append(m)
    echo("  Unresolved markers:")
    # Stable display order: warn-severity tokens first, then info, then alpha.
    ordered = sorted(
        by_token.items(),
        key=lambda kv: (kv[1][0].severity != "warn", kv[0]),
    )
    for token, hits in ordered:
        sev_tag = "" if hits[0].severity == "warn" else " (info)"
        if include_locations:
            locs = ", ".join(f"{m.file}:{m.line}" for m in hits)
            echo(f"    {len(hits)}x {token}{sev_tag} ({locs})")
        else:
            echo(f"    {len(hits)}x {token}{sev_tag}")


@refs_group.command("check")
@click.option("--root", "root_path", default=".", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option("--strict", is_flag=True, help="Exit with error on any broken ref (not just markers)")
@click.option("--summary-only", is_flag=True, help="Print only aggregate counts, not individual references.")
@click.option(
    "--type",
    "ref_types",
    multiple=True,
    help="Only report refs of this type. Can be passed more than once, e.g. --type task --type link.",
)
@click.option("--by-value", is_flag=True, help="Include duplicate counts grouped by reference value.")
@click.option(
    "--include-body",
    is_flag=True,
    help="Additionally scan body prose for typed `<kind>:<slug>` refs (not just frontmatter).",
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted refs report to PATH instead of stdout.",
)
def check(
    root_path: Path,
    output_format: str,
    strict: bool,
    summary_only: bool,
    ref_types: tuple[str, ...],
    by_value: bool,
    include_body: bool,
    output_path: Path | None,
) -> None:
    """Scan project documents for broken cross-references."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.refs_projection import project_refs_check

    try:
        issues = check_refs(root_path.resolve(), include_body=include_body)
    except PeerUnresolved as exc:
        raise click.ClickException(str(exc)) from exc

    filtered = _filter_issues_by_type(issues, ref_types)
    broken = [i for i in filtered if i.ref_type != "marker"]
    markers = [i for i in filtered if i.ref_type == "marker"]

    if strict:
        # Under --strict, info-severity markers (SPECULATION, INACCESSIBLE)
        # are promoted to warn so they display without the (info) tag and
        # contribute to the existing strict-exit policy below.
        from science_tool.markers import severity_for

        for issue in markers:
            if issue.severity == "info":
                token = issue.ref_value.strip("[]")
                issue.severity = severity_for(token, strict=True)

    summary = _refs_summary(broken, markers, by_value=by_value)

    json_summary: dict[str, Any] = {
        "broken": summary["broken"],
        "markers": summary["markers"],
        "by_type": summary["by_type"],
    }
    if by_value:
        json_summary["by_value"] = summary["by_value"]
    full: dict[str, Any] = {"summary": json_summary}
    if not summary_only:
        full.update(
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

    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("refs-check", output_format))
    sink = BoundedSink(
        lookup("refs check"), output_path=output_path, command_path="refs check", complete_via=complete_via
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete refs report to {output_path}") if output_path is not None else None
    )

    displayed = full if output_path is not None else project_refs_check(full)
    broken_omitted = displayed.get("broken_omitted", 0)
    markers_omitted = displayed.get("markers_omitted", 0)
    if output_path is None and (broken_omitted or markers_omitted):
        truncation: dict[str, Any] = {"complete_via": complete_via}
        if broken_omitted:
            truncation["broken"] = {"omitted": broken_omitted, "total": len(broken)}
        if markers_omitted:
            truncation["markers"] = {"omitted": markers_omitted, "total": len(markers)}
        displayed = {**displayed, "truncation": truncation}

    # Markers shown in the by-token text summary are capped to match the JSON `markers`
    # list; `--summary-only` never emits that list, so the by-token summary stays uncapped
    # there -- it groups by a small, bounded marker-token vocabulary, not one row per hit.
    markers_shown = markers if summary_only or output_path is not None else markers[: len(displayed["markers"])]

    def _render_human() -> None:
        if broken:
            sink.echo(f"refs check: {len(broken)} broken, {len(markers)} unresolved markers\n")
            sink.echo("By type:")
            for ref_type, count in summary["by_type"].items():
                sink.echo(f"  {ref_type}: {count}")
            sink.echo()
            if by_value:
                sink.echo("By value:")
                for ref_value, count in summary["by_value"].items():
                    sink.echo(f"  {ref_value}: {count}")
                sink.echo()
            if not summary_only:
                for issue in displayed["broken"]:
                    sink.echo(f"  {issue['file']}:{issue['line']}")
                    sink.echo(f"    {issue['message']}")
                    if issue["suggestion"]:
                        sink.echo(f"    Suggestion: {issue['suggestion']}")
                    sink.echo()
                if broken_omitted:
                    sink.echo(f"showing {len(displayed['broken'])} of {len(broken)} broken refs")
                    sink.echo(f"  complete output:  {complete_via}")
        elif markers:
            sink.echo(f"refs check: 0 broken, {len(markers)} unresolved markers\n")
        else:
            sink.echo("refs check: all references valid, no unresolved markers")
            return

        if markers:
            _render_marker_summary(markers_shown, include_locations=not summary_only, echo=sink.echo)
            if markers_omitted:
                sink.echo(f"showing {len(markers_shown)} of {len(markers)} unresolved markers")
                sink.echo(f"  complete output:  {complete_via}")

    emit(output_format=output_format, payload=displayed, render_text=_render_human, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)

    if broken:
        raise click.exceptions.Exit(1)
    if strict and markers:
        raise click.exceptions.Exit(1)


