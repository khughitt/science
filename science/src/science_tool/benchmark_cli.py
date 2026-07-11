"""`science benchmark` command group — benchmark dataset reports."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any, cast

import click

from science_tool.output import emit


def _project_root_from_env() -> Path:
    """Return project root from SCIENCE_PROJECT_ROOT env var or cwd."""
    import os

    env = os.environ.get("SCIENCE_PROJECT_ROOT")
    return Path(env).resolve() if env else Path.cwd()


@click.group("benchmark")
def benchmark_group() -> None:
    """Benchmark dataset reports."""


@benchmark_group.command("list")
@click.option("--domain", default=None, help="Filter by benchmark domain.")
@click.option("--kind", "benchmark_kind", default=None, help="Filter by benchmark kind.")
@click.option("--belief-ref-text", default=None, help="Filter by exact related-belief text token.")
@click.option("--commons", "include_commons", is_flag=True, help="Also list commons benchmark dataset entities.")
@click.option("--coverage-summary", "coverage_summary_flag", is_flag=True, help="Only report coverage summary counts.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd).",
)
def benchmark_list(
    domain: str | None,
    benchmark_kind: str | None,
    belief_ref_text: str | None,
    include_commons: bool,
    coverage_summary_flag: bool,
    output_format: str,
    project_root: Path | None,
) -> None:
    """List dataset entities with benchmark metadata."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_catalog import coverage_summary, list_benchmarks

    root = project_root.resolve() if project_root else _project_root_from_env()
    rows, notice = list_benchmarks(
        root,
        domain=domain,
        benchmark_kind=benchmark_kind,
        belief_ref_text=belief_ref_text,
        include_commons=include_commons,
    )
    summary = coverage_summary(rows)

    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    def _render() -> None:
        if coverage_summary_flag:
            table = Table(show_header=True, header_style="bold")
            for col in ("facet", "value", "count"):
                table.add_column(col, overflow="fold", no_wrap=False)
            for facet, counts in summary.items():
                for value, count in counts.items():
                    table.add_row(facet, value, str(count))
            Console(width=200).print(table)
            return

        if not rows:
            click.echo("No matching benchmark dataset entities.")
            return

        table = Table(show_header=True, header_style="bold")
        for col in ("id", "title", "scope", "class", "domains", "modalities", "signal_types", "kinds", "tasks"):
            table.add_column(col, overflow="fold", no_wrap=False)
        for row in rows:
            table.add_row(
                row["id"],
                row["title"],
                row["scope"],
                row["dataset_class"],
                ", ".join(row["domains"]),
                ", ".join(row["modalities"]),
                ", ".join(row["signal_types"]),
                ", ".join(row["benchmark_kinds"]),
                ", ".join(row["task_ids"]),
            )
        Console(width=200).print(table)

    if coverage_summary_flag:
        payload = {"summary": summary, "commons_notice": notice}
    else:
        payload = {"rows": rows, "summary": summary, "commons_notice": notice}
    emit(output_format=output_format, payload=payload, render_text=_render, sort_keys=True)


@benchmark_group.command("opportunities")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--entity", "entity_ref", default=None, help="Limit report to one project entity reference.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option("--calibration-report", is_flag=True, help="Include token/scoring calibration details.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd).",
)
def benchmark_opportunities(
    domain: str | None,
    entity_ref: str | None,
    include_commons: bool,
    calibration_report: bool,
    output_format: str,
    project_root: Path | None,
) -> None:
    """Report candidate benchmark opportunities for project entities."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_opportunities import opportunity_report
    from science_tool.entities import EntityCommandError, resolve_entity_ref

    root = project_root.resolve() if project_root else _project_root_from_env()
    entity_id: str | None = None
    if entity_ref is not None:
        try:
            entity_id = resolve_entity_ref(root, entity_ref)
        except EntityCommandError as exc:
            raise click.ClickException(str(exc)) from exc

    try:
        payload = opportunity_report(
            root,
            include_commons=include_commons,
            entity_id=entity_id,
            domain=domain,
            calibration_report=calibration_report,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    notice = payload["commons_notice"]
    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    def _render() -> None:
        rows = payload["matched_opportunities"]
        if not rows:
            click.echo("No candidate benchmark opportunities.")
        else:
            table = Table(title="Candidate Opportunities", show_header=True, header_style="bold")
            for col in ("entity", "benchmark", "task", "relative", "baseline", "reasons"):
                table.add_column(col, overflow="fold", no_wrap=False)
            for row in rows:
                table.add_row(
                    row["entity_id"],
                    row["benchmark_id"],
                    row["task_id"] or "-",
                    str(row["relative_score"]),
                    str(row["baseline_score"]),
                    ", ".join(row["match_reasons"]),
                )
            Console(width=200).print(table)

        if calibration_report:
            calibration_table = Table(title="Calibration", show_header=True, header_style="bold")
            calibration_table.add_column("field", overflow="fold", no_wrap=False)
            calibration_table.add_column("value", overflow="fold", no_wrap=False)
            for field, value in payload["calibration"].items():
                calibration_table.add_row(field, json.dumps(value, sort_keys=True))
            Console(width=200).print(calibration_table)

    emit(output_format=output_format, payload=payload, render_text=_render, sort_keys=True)


def _parse_project_specs(project_specs: tuple[str, ...]) -> list[tuple[str, Path]]:
    if not project_specs:
        raise click.ClickException("at least one --project label=path is required")
    parsed: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for spec in project_specs:
        if "=" not in spec:
            raise click.ClickException("--project must use label=path")
        label, raw_path = spec.split("=", 1)
        label = label.strip()
        if not label:
            raise click.ClickException("--project label must be non-empty")
        if label in seen:
            raise click.ClickException(f"duplicate --project label: {label}")
        path = Path(raw_path).expanduser().resolve()
        if not path.is_dir():
            raise click.ClickException(f"--project {label} path does not exist: {path}")
        seen.add(label)
        parsed.append((label, path))
    return parsed


def _format_count_rows(rows: Sequence[Mapping[str, Any]], *, key: str) -> str:
    values = [f"{row[key]}:{row['count']}" for row in rows]
    return ", ".join(values) if values else "-"


def _format_count_map(counts: Mapping[str, int]) -> str:
    rows = [{"key": key, "count": count} for key, count in counts.items() if count]
    return _format_count_rows(rows, key="key") if rows else "-"


def _format_share_rows(rows: Sequence[Mapping[str, Any]], *, key: str) -> str:
    values = [f"{row[key]}:{row['count']} ({row['share']})" for row in rows]
    return ", ".join(values) if values else "-"


@benchmark_group.command("gap-calibration")
@click.option("--project", "project_specs", multiple=True, help="Project as label=path. Repeat for each project.")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--facet", default=None, help="Limit gaps to a high-value missing benchmark facet.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
def benchmark_gap_calibration(
    project_specs: tuple[str, ...],
    domain: str | None,
    facet: str | None,
    include_commons: bool,
    output_format: str,
) -> None:
    """Summarize benchmark gap calibration across projects."""
    from science_tool.benchmark_opportunities import benchmark_gap_calibration_batch

    projects = _parse_project_specs(project_specs)
    try:
        payload = benchmark_gap_calibration_batch(
            projects,
            include_commons=include_commons,
            domain=domain,
            facet=facet,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    def _render() -> None:
        from rich.console import Console
        from rich.table import Table

        table = Table(title="Benchmark Gap Calibration", show_header=True, header_style="bold")
        for col in (
            "project",
            "gap rows",
            "entity candidates",
            "fallback candidates",
            "fallback ratio",
            "suggested facets",
            "matched facets",
            "fallback benchmarks",
        ):
            table.add_column(col, overflow="fold", no_wrap=False)
        for project in payload["projects"]:
            summary = project["calibration_summary"]
            ratio = "-"
            if summary["candidate_rows"]:
                ratio = f"{summary['fallback_candidate_rows'] / summary['candidate_rows']:.3f}"
            table.add_row(
                project["label"],
                str(summary["gap_rows"]),
                str(summary["entity_specific_candidate_rows"]),
                str(summary["fallback_candidate_rows"]),
                ratio,
                _format_count_rows(summary["top_suggested_facets"], key="facet"),
                _format_count_rows(summary["top_matched_hint_facets"], key="facet"),
                _format_count_rows(summary["top_fallback_benchmarks"], key="benchmark_id"),
            )
        Console(width=200).print(table)

        aggregate_table = Table(title="Aggregate Benchmark Gap Calibration", show_header=True, header_style="bold")
        aggregate_table.add_column("field", overflow="fold", no_wrap=False)
        aggregate_table.add_column("value", overflow="fold", no_wrap=False)
        aggregate = payload["aggregate"]
        for field in (
            "project_count",
            "gap_rows",
            "candidate_rows",
            "entity_specific_candidate_rows",
            "fallback_candidate_rows",
            "fallback_candidate_ratio",
        ):
            aggregate_table.add_row(field, str(aggregate[field]))
        aggregate_table.add_row(
            "top_suggested_facets",
            _format_count_rows(aggregate["top_suggested_facets"], key="facet"),
        )
        aggregate_table.add_row(
            "top_matched_hint_facets",
            _format_count_rows(aggregate["top_matched_hint_facets"], key="facet"),
        )
        aggregate_table.add_row(
            "top_fallback_benchmarks",
            _format_count_rows(aggregate["top_fallback_benchmarks"], key="benchmark_id"),
        )
        aggregate_table.add_row(
            "top_fallback_reasons",
            _format_count_rows(aggregate["top_fallback_reasons"], key="reason"),
        )
        aggregate_table.add_row(
            "top_fallback_selection_reasons",
            _format_count_rows(aggregate["top_fallback_selection_reasons"], key="reason"),
        )
        aggregate_table.add_row(
            "top_fallback_benchmark_shares",
            _format_share_rows(aggregate["top_fallback_benchmark_shares"], key="benchmark_id"),
        )
        aggregate_table.add_row("fallback_concentration_warning", str(aggregate["fallback_concentration_warning"]))
        Console(width=200).print(aggregate_table)

    emit(output_format=output_format, payload=payload, render_text=_render, sort_keys=True)


@benchmark_group.command("tests")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--entity", "entity_ref", default=None, help="Limit report to one project entity reference.")
@click.option("--facet", default=None, help="Limit plans to a benchmark facet.")
@click.option(
    "--state", type=click.Choice(["concrete", "draft-needed"]), default=None, help="Filter by test plan state."
)
@click.option(
    "--source",
    "priority_source",
    type=click.Choice(["opportunity-relative", "gap-candidate", "gap-fallback"]),
    default=None,
    help="Filter by benchmark test priority source.",
)
@click.option("--exclude-fallback", is_flag=True, help="Drop broad fallback benchmark rows.")
@click.option(
    "--readiness",
    "readiness_label",
    type=click.Choice(["runnable", "stage-needed", "metadata-only", "blocked"]),
    default=None,
    help="Filter by benchmark runtime/readiness label.",
)
@click.option("--runnable-only", is_flag=True, help="Shortcut for --readiness runnable.")
@click.option("--benchmark", "benchmark_ref", default=None, help="Filter by benchmark dataset id or slug.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option(
    "--context-fit",
    "context_fit",
    multiple=True,
    type=click.Choice(
        ["direct-fit", "adjacent-fit", "method-fit", "blocked-fit", "generic-fallback", "out-of-context"]
    ),
    help="Filter by benchmark context-fit label. May be supplied more than once.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd).",
)
def benchmark_tests(
    domain: str | None,
    entity_ref: str | None,
    facet: str | None,
    state: str | None,
    priority_source: str | None,
    exclude_fallback: bool,
    readiness_label: str | None,
    runnable_only: bool,
    benchmark_ref: str | None,
    include_commons: bool,
    context_fit: tuple[str, ...],
    output_format: str,
    project_root: Path | None,
) -> None:
    """Report benchmark test plans for project entities."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_opportunities import TestPlanState, benchmark_tests_report
    from science_tool.entities import EntityCommandError, resolve_entity_ref

    root = project_root.resolve() if project_root else _project_root_from_env()
    entity_id: str | None = None
    if entity_ref is not None:
        try:
            entity_id = resolve_entity_ref(root, entity_ref)
        except EntityCommandError as exc:
            raise click.ClickException(str(exc)) from exc
    if runnable_only and readiness_label not in {None, "runnable"}:
        raise click.ClickException(f"--runnable-only conflicts with --readiness {readiness_label}")

    try:
        payload = benchmark_tests_report(
            root,
            include_commons=include_commons,
            entity_id=entity_id,
            domain=domain,
            facet=facet,
            state=cast("TestPlanState | None", state),
            source=cast("Any", priority_source),
            exclude_fallback=exclude_fallback,
            readiness="runnable" if runnable_only else cast("Any", readiness_label),
            benchmark_id=benchmark_ref,
            context_fit=context_fit or None,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    notice = payload["commons_notice"]
    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    def _render() -> None:
        rows = payload["benchmark_tests"]
        if not rows:
            click.echo("No benchmark test plans.")
            return

        table = Table(title="Benchmark Tests", show_header=True, header_style="bold")
        for col in (
            "entity",
            "state",
            "source",
            "readiness",
            "fit",
            "benchmark",
            "task",
            "score",
            "facets",
            "needs",
        ):
            table.add_column(col, overflow="fold", no_wrap=False)
        for row in rows:
            table.add_row(
                row["entity_id"],
                row["test_plan_state"],
                row["priority_source"],
                row["readiness_label"],
                row["context_fit"],
                row["benchmark_id"],
                row["task_id"] or "-",
                str(row["priority_score"]),
                ", ".join(row["matched_facets"]) or "-",
                ", ".join(row["needs"]) or "-",
            )
        Console(width=200).print(table)

    emit(output_format=output_format, payload=payload, render_text=_render, sort_keys=True)


@benchmark_group.command("test-triage")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--entity", "entity_ref", default=None, help="Limit report to one project entity reference.")
@click.option("--facet", default=None, help="Limit plans to a benchmark facet.")
@click.option(
    "--state", type=click.Choice(["concrete", "draft-needed"]), default=None, help="Filter by test plan state."
)
@click.option(
    "--source",
    "priority_source",
    type=click.Choice(["opportunity-relative", "gap-candidate", "gap-fallback"]),
    default=None,
    help="Filter by benchmark test priority source.",
)
@click.option("--exclude-fallback", is_flag=True, help="Drop broad fallback benchmark rows.")
@click.option(
    "--include-blocked-fallback",
    is_flag=True,
    help="Include gap-fallback rows for blocked task-support tasks in triage output.",
)
@click.option(
    "--readiness",
    "readiness_label",
    type=click.Choice(["runnable", "stage-needed", "metadata-only", "blocked"]),
    default=None,
    help="Filter by benchmark runtime/readiness label.",
)
@click.option("--runnable-only", is_flag=True, help="Shortcut for --readiness runnable.")
@click.option("--benchmark", "benchmark_ref", default=None, help="Filter by benchmark dataset id or slug.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option(
    "--context-fit",
    "context_fit",
    multiple=True,
    type=click.Choice(
        ["direct-fit", "adjacent-fit", "method-fit", "blocked-fit", "generic-fallback", "out-of-context"]
    ),
    help="Filter by benchmark context-fit label. May be supplied more than once.",
)
@click.option("--write-review-file", is_flag=True, help="Write a YAML review artifact under the project root.")
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(path_type=Path, file_okay=True, dir_okay=False),
    help="Review artifact path. Relative paths are resolved under the project root.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd).",
)
def benchmark_test_triage(
    domain: str | None,
    entity_ref: str | None,
    facet: str | None,
    state: str | None,
    priority_source: str | None,
    exclude_fallback: bool,
    include_blocked_fallback: bool,
    readiness_label: str | None,
    runnable_only: bool,
    benchmark_ref: str | None,
    include_commons: bool,
    context_fit: tuple[str, ...],
    write_review_file: bool,
    output_path: Path | None,
    output_format: str,
    project_root: Path | None,
) -> None:
    """Report benchmark test plans grouped for action triage."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_opportunities import (
        TestPlanState,
        benchmark_test_triage_report,
        write_test_triage_review_file,
    )
    from science_tool.entities import EntityCommandError, resolve_entity_ref

    if output_path is not None and not write_review_file:
        raise click.ClickException("--output requires --write-review-file")

    root = project_root.resolve() if project_root else _project_root_from_env()
    entity_id: str | None = None
    if entity_ref is not None:
        try:
            entity_id = resolve_entity_ref(root, entity_ref)
        except EntityCommandError as exc:
            raise click.ClickException(str(exc)) from exc
    if runnable_only and readiness_label not in {None, "runnable"}:
        raise click.ClickException(f"--runnable-only conflicts with --readiness {readiness_label}")

    try:
        payload = benchmark_test_triage_report(
            root,
            include_commons=include_commons,
            entity_id=entity_id,
            domain=domain,
            facet=facet,
            state=cast("TestPlanState | None", state),
            source=cast("Any", priority_source),
            exclude_fallback=exclude_fallback,
            include_blocked_fallback=include_blocked_fallback,
            readiness="runnable" if runnable_only else cast("Any", readiness_label),
            benchmark_id=benchmark_ref,
            context_fit=context_fit or None,
        )
        if write_review_file:
            generated = _benchmark_test_triage_today()
            review_path = write_test_triage_review_file(
                payload=payload,
                project_root=root,
                output_path=output_path,
                generated=generated,
                source_command=_test_triage_source_command(
                    include_commons=include_commons,
                    domain=domain,
                    entity_ref=entity_ref,
                    facet=facet,
                    state=state,
                    priority_source=priority_source,
                    exclude_fallback=exclude_fallback,
                    include_blocked_fallback=include_blocked_fallback,
                    readiness_label=readiness_label,
                    runnable_only=runnable_only,
                    benchmark_ref=benchmark_ref,
                    context_fit=context_fit,
                    output_format=output_format,
                ),
            )
            payload["review_file"] = str(review_path)
            click.echo(f"wrote benchmark test triage review file: {review_path}", err=True)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    notice = payload["commons_notice"]
    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    def _render() -> None:
        visible_rows = 0
        for bucket in ("run-now", "stage-next", "metadata-needed", "blocked-or-reference"):
            bucket_rows = payload["buckets"][bucket][:10]
            if not bucket_rows:
                continue
            table = Table(title=f"Benchmark Test Triage: {bucket}", show_header=True, header_style="bold")
            for col in ("entity", "benchmark", "task", "fit", "readiness", "score", "facets", "needs"):
                table.add_column(col, overflow="fold", no_wrap=False)
            for row in bucket_rows:
                visible_rows += 1
                table.add_row(
                    row["entity_id"],
                    row["benchmark_id"],
                    _format_test_triage_task(row),
                    row["context_fit"],
                    row["readiness_label"],
                    str(row["priority_score"]),
                    _format_test_triage_facets(row),
                    _format_test_triage_needs(row),
                )
            Console(width=200).print(table)
        fallback_count = payload["summary"]["bucket_counts"]["fallback-diagnostic"]
        if fallback_count:
            from science_tool.benchmark_opportunities import (
                FALLBACK_DISPLAY_GROUPS,
                _is_generic_fallback_display_group,
            )

            diagnostics = payload["fallback_diagnostics"]
            rollups = diagnostics["rollups"]
            for rollup in rollups:
                display_group = rollup.get("display_group")
                if display_group not in FALLBACK_DISPLAY_GROUPS:
                    raise click.ClickException(f"unknown fallback display group: {display_group}")
            visible_terminal_rollups = [
                rollup for rollup in rollups if not _is_generic_fallback_display_group(rollup["display_group"])
            ]
            visible_rollups = visible_terminal_rollups[:10]
            terminal_visible_total = diagnostics.get("terminal_visible_rollup_count", len(rollups))
            if terminal_visible_total > 0 and not visible_rollups:
                raise click.ClickException("fallback diagnostics rollups missing for fallback rows")
            if visible_rollups:
                table = Table(title="Benchmark Test Triage: fallback-diagnostic", show_header=True, header_style="bold")
                for col in ("rows", "benchmark", "task", "support", "readiness", "class", "facets", "examples"):
                    table.add_column(col, overflow="fold", no_wrap=False)
                shown_fallback_rows = diagnostics.get("shown_fallback_rows", fallback_count)
                row_label = f"{shown_fallback_rows} fallback rows grouped into {len(visible_terminal_rollups)} rollups"
                if len(visible_rollups) < len(visible_terminal_rollups):
                    hidden_rollups = len(visible_terminal_rollups) - len(visible_rollups)
                    row_label = f"{row_label} (showing {len(visible_rollups)}, {hidden_rollups} hidden)"
                for index, rollup in enumerate(visible_rollups):
                    table.add_row(
                        row_label if index == 0 else "",
                        str(rollup.get("benchmark_id") or "-"),
                        _format_test_triage_rollup_task(rollup),
                        _format_test_triage_rollup_support(rollup),
                        str(rollup.get("readiness_label") or "-"),
                        str(rollup.get("dataset_class") or "-"),
                        _format_test_triage_rollup_facets(rollup),
                        _format_test_triage_rollup_examples(rollup),
                    )
                Console(width=200).print(table)
                visible_rows += len(visible_rollups)
            hidden_generic_fallback_rows = diagnostics.get("hidden_generic_fallback_rows", 0)
            if hidden_generic_fallback_rows:
                table = Table(
                    title="Benchmark Test Triage: generic fallback summary",
                    show_header=True,
                    header_style="bold",
                )
                for col in ("rows", "top benchmarks", "top reasons"):
                    table.add_column(col, overflow="fold", no_wrap=False)
                table.add_row(
                    f"{hidden_generic_fallback_rows} generic fallback rows hidden from detailed table",
                    _format_count_rows(diagnostics.get("top_generic_fallback_benchmarks", []), key="benchmark_id"),
                    _format_count_rows(diagnostics.get("top_generic_fallback_reasons", []), key="reason"),
                )
                Console(width=200).print(table)
                visible_rows += 1
        suppressed = payload["fallback_diagnostics"].get("suppressed_blocked_support")
        if suppressed:
            table = Table(
                title="Benchmark Test Triage: suppressed blocked fallback",
                show_header=True,
                header_style="bold",
            )
            for col in ("rows", "top benchmarks"):
                table.add_column(col, overflow="fold", no_wrap=False)
            table.add_row(
                f"Suppressed {suppressed['rows']} fallback rows for blocked task support",
                _format_count_rows(suppressed["top_benchmarks"], key="benchmark_id"),
            )
            Console(width=200).print(table)
            visible_rows += 1
        if not visible_rows:
            click.echo("No benchmark test triage rows.")
            return

    emit(output_format=output_format, payload=payload, render_text=_render, sort_keys=True)


def _format_gap_candidate_for_table(candidate: Mapping[str, Any]) -> str:
    context_fit = candidate.get("context_fit")
    label = f" \\[{context_fit}]" if context_fit else ""
    return f"{candidate['benchmark_id']}{label} ({candidate['candidate_score']})"


def _format_gap_candidates_for_table(row: Mapping[str, Any]) -> str:
    candidates = row["candidate_benchmarks"]
    if not candidates:
        return "-"
    fallback_candidates = [
        candidate
        for candidate in candidates
        if any(str(note).startswith("fallback:") for note in candidate.get("reason_notes", []))
    ]
    if fallback_candidates and len(fallback_candidates) != len(candidates):
        raise ValueError("gap row mixes entity-specific and fallback candidates")
    if row.get("candidate_mode") != "fallback-only":
        return ", ".join(_format_gap_candidate_for_table(candidate) for candidate in candidates[:3])

    from science_tool.benchmark_opportunities import (
        _fallback_display_group_for_gap_candidate,
        _is_generic_fallback_display_group,
    )

    rendered: list[str] = []
    generic_candidates: list[Mapping[str, Any]] = []
    for candidate in candidates:
        display_group = _fallback_display_group_for_gap_candidate(candidate)
        if _is_generic_fallback_display_group(display_group):
            generic_candidates.append(candidate)
        else:
            rendered.append(_format_gap_candidate_for_table(candidate))
    if generic_candidates:
        top_benchmark = generic_candidates[0]["benchmark_id"]
        rendered.append(f"generic fallback: {len(generic_candidates)} candidates (top: {top_benchmark})")
    return ", ".join(rendered) if rendered else "-"


def _format_test_triage_task(row: Mapping[str, Any]) -> str:
    task_id = row.get("task_id")
    return str(task_id) if task_id else "-"


def _format_test_triage_needs(row: Mapping[str, Any]) -> str:
    needs = row.get("needs") or []
    return ", ".join(str(need) for need in needs) if needs else "-"


def _format_test_triage_facets(row: Mapping[str, Any]) -> str:
    facets = row.get("matched_facets") or []
    return ", ".join(str(facet) for facet in facets) if facets else "-"


def _format_test_triage_rollup_task(rollup: Mapping[str, Any]) -> str:
    task_id = rollup.get("task_id")
    if not task_id:
        return "-"
    task = str(task_id).split("#", 1)[-1]
    task_type = str(rollup.get("task_type") or "")
    return f"{task} ({task_type})" if task_type else task


def _format_test_triage_rollup_support(rollup: Mapping[str, Any]) -> str:
    state = str(rollup.get("task_support_state") or "none")
    reason = str(rollup.get("task_support_reason") or "")
    return f"{state}: {reason}" if reason else state


def _format_test_triage_rollup_facets(rollup: Mapping[str, Any]) -> str:
    return _format_count_rows(rollup.get("top_facets", []), key="facet")


def _format_test_triage_rollup_examples(rollup: Mapping[str, Any]) -> str:
    examples = [str(entity_id) for entity_id in rollup.get("example_entities", [])]
    return ", ".join(examples) if examples else "-"


def _format_hint_candidate_count(row: Mapping[str, Any]) -> str:
    count = row["count"]
    return "-" if count is None else str(count)


def _hint_candidate_table_rows(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if row["category"] == "domain-candidate"]


def _benchmark_hint_candidates_today() -> date:
    return date.today()


def _hint_candidates_source_command(
    *,
    include_commons: bool,
    domain: str | None,
    min_count: int,
    include_existing: bool,
    output_format: str,
) -> str:
    # Best-effort context string for review artifacts, not an exact shell history record.
    parts = ["science", "benchmark", "hint-candidates"]
    if include_commons:
        parts.append("--commons")
    if domain is not None:
        parts.extend(["--domain", domain])
    if min_count != 1:
        parts.extend(["--min-count", str(min_count)])
    if include_existing:
        parts.append("--include-existing")
    if output_format != "table":
        parts.extend(["--format", output_format])
    parts.append("--write-review-file")
    return " ".join(parts)


def _benchmark_test_triage_today() -> date:
    return date.today()


def _test_triage_source_command(
    *,
    include_commons: bool,
    domain: str | None,
    entity_ref: str | None,
    facet: str | None,
    state: str | None,
    priority_source: str | None,
    exclude_fallback: bool,
    include_blocked_fallback: bool,
    readiness_label: str | None,
    runnable_only: bool,
    benchmark_ref: str | None,
    context_fit: tuple[str, ...],
    output_format: str,
) -> str:
    # Best-effort context string for review artifacts, not an exact shell history record.
    parts = ["science", "benchmark", "test-triage"]
    if include_commons:
        parts.append("--commons")
    if domain is not None:
        parts.extend(["--domain", domain])
    if entity_ref is not None:
        parts.extend(["--entity", entity_ref])
    if facet is not None:
        parts.extend(["--facet", facet])
    if state is not None:
        parts.extend(["--state", state])
    if priority_source is not None:
        parts.extend(["--source", priority_source])
    if exclude_fallback:
        parts.append("--exclude-fallback")
    if include_blocked_fallback:
        parts.append("--include-blocked-fallback")
    if readiness_label is not None:
        parts.extend(["--readiness", readiness_label])
    if runnable_only:
        parts.append("--runnable-only")
    if benchmark_ref is not None:
        parts.extend(["--benchmark", benchmark_ref])
    for value in context_fit:
        parts.extend(["--context-fit", value])
    if output_format != "table":
        parts.extend(["--format", output_format])
    parts.append("--write-review-file")
    return " ".join(parts)


@benchmark_group.command("hint-candidates")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option(
    "--min-count", default=1, type=click.IntRange(min=1), show_default=True, help="Minimum visible term count."
)
@click.option("--include-existing", is_flag=True, help="Include terms already mapped by the benchmark hint lexicon.")
@click.option("--write-review-file", is_flag=True, help="Write a YAML review artifact under the project root.")
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(path_type=Path, file_okay=True, dir_okay=False),
    help="Review artifact path. Relative paths are resolved under the project root.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd).",
)
def benchmark_hint_candidates(
    domain: str | None,
    include_commons: bool,
    min_count: int,
    include_existing: bool,
    write_review_file: bool,
    output_path: Path | None,
    output_format: str,
    project_root: Path | None,
) -> None:
    """Report candidate terms for benchmark facet hint review."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_opportunities import (
        benchmark_hint_candidates_report,
        write_hint_candidates_review_file,
    )

    if output_path is not None and not write_review_file:
        raise click.ClickException("--output requires --write-review-file")

    root = project_root.resolve() if project_root else _project_root_from_env()
    generated = _benchmark_hint_candidates_today()
    try:
        payload = benchmark_hint_candidates_report(
            root,
            include_commons=include_commons,
            domain=domain,
            min_count=min_count,
            include_existing=include_existing,
        )
        if write_review_file:
            review_path = write_hint_candidates_review_file(
                payload=payload,
                project_root=root,
                output_path=output_path,
                generated=generated,
                source_command=_hint_candidates_source_command(
                    include_commons=include_commons,
                    domain=domain,
                    min_count=min_count,
                    include_existing=include_existing,
                    output_format=output_format,
                ),
            )
            payload = {**payload, "review_file": str(review_path)}
            click.echo(f"wrote benchmark hint candidate review file: {review_path}", err=True)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    notice = payload["commons_notice"]
    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    def _render() -> None:
        rows = _hint_candidate_table_rows(payload["hint_candidates"])
        if not rows:
            click.echo("No benchmark hint candidates.")
            return

        table = Table(title="Benchmark Hint Candidates", show_header=True, header_style="bold")
        for col in ("term", "count", "action", "suggested facets", "examples"):
            table.add_column(col, overflow="fold", no_wrap=False)
        for row in rows:
            table.add_row(
                row["term"],
                _format_hint_candidate_count(row),
                row["suggested_action"],
                ", ".join(row["suggested_facets"]) or "-",
                ", ".join(row["example_entities"]) or "-",
            )
        Console(width=200).print(table)

    emit(output_format=output_format, payload=payload, render_text=_render, sort_keys=True)


@benchmark_group.command("gaps")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--entity", "entity_ref", default=None, help="Limit report to one project entity reference.")
@click.option("--facet", default=None, help="Limit gaps to a high-value missing benchmark facet.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option("--calibration-report", is_flag=True, help="Include gap token/candidate calibration details.")
@click.option("--calibration-summary", is_flag=True, help="Summarize benchmark gap calibration metrics.")
@click.option("--evidence-report", is_flag=True, help="Include benchmark gap evidence extraction details.")
@click.option(
    "--context-fit",
    "context_fit",
    multiple=True,
    type=click.Choice(
        ["direct-fit", "adjacent-fit", "method-fit", "blocked-fit", "generic-fallback", "out-of-context"]
    ),
    help="Filter by benchmark context-fit label. May be supplied more than once.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd).",
)
def benchmark_gaps(
    domain: str | None,
    entity_ref: str | None,
    facet: str | None,
    include_commons: bool,
    calibration_report: bool,
    calibration_summary: bool,
    evidence_report: bool,
    context_fit: tuple[str, ...],
    output_format: str,
    project_root: Path | None,
) -> None:
    """Report benchmark coverage gaps for project entities."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_opportunities import gap_calibration_summary, gaps_report
    from science_tool.entities import EntityCommandError, resolve_entity_ref

    root = project_root.resolve() if project_root else _project_root_from_env()
    entity_id: str | None = None
    if entity_ref is not None:
        try:
            entity_id = resolve_entity_ref(root, entity_ref)
        except EntityCommandError as exc:
            raise click.ClickException(str(exc)) from exc

    try:
        payload = gaps_report(
            root,
            include_commons=include_commons,
            entity_id=entity_id,
            domain=domain,
            facet=facet,
            calibration_report=calibration_report,
            evidence_report=evidence_report,
            context_fit=context_fit or None,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    notice = payload["commons_notice"]
    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    summary_payload = gap_calibration_summary(payload) if calibration_summary else None
    output_payload: dict[str, object] = dict(payload)
    if summary_payload is not None:
        output_payload["calibration_summary"] = summary_payload

    def _render() -> None:
        rows = payload["benchmark_gaps"]
        if not rows:
            click.echo("No benchmark gaps.")
        else:
            table = Table(title="Benchmark Gaps", show_header=True, header_style="bold")
            for col in ("entity", "level", "mode", "missing facets", "matches", "candidates", "reason"):
                table.add_column(col, overflow="fold", no_wrap=False)
            for row in rows:
                missing = ", ".join(row["missing_modalities"] + row["missing_signal_types"]) or "-"
                table.add_row(
                    row["entity_id"],
                    row["gap_level"],
                    row["candidate_mode"],
                    missing,
                    str(len(row["current_matches"])),
                    _format_gap_candidates_for_table(row),
                    row["reason"],
                )
            Console(width=200).print(table)
        generic_fallback_rows = payload["fallback_diagnostics"]["generic_fallback_candidate_rows"]
        if generic_fallback_rows:
            click.echo(
                f"Collapsed {generic_fallback_rows} generic fallback candidates; "
                "use --calibration-summary or --format json for diagnostics."
            )

        if summary_payload is not None:
            summary_table = Table(title="Gap Calibration Summary", show_header=True, header_style="bold")
            summary_table.add_column("field", overflow="fold", no_wrap=False)
            summary_table.add_column("value", overflow="fold", no_wrap=False)
            score_range = (
                "-"
                if summary_payload["score_min"] is None
                else (
                    f"{summary_payload['score_min']} / "
                    f"{summary_payload['score_median']} / {summary_payload['score_max']}"
                )
            )
            scalar_rows = {
                "gap_rows": summary_payload["gap_rows"],
                "rows_with_suggested_facets": summary_payload["rows_with_suggested_facets"],
                "candidate_rows": summary_payload["candidate_rows"],
                "entity_specific_candidate_rows": summary_payload["entity_specific_candidate_rows"],
                "fallback_candidate_rows": summary_payload["fallback_candidate_rows"],
                "score_min_median_max": score_range,
                "top_suggested_facets": summary_payload["top_suggested_facets"],
                "top_matched_hint_facets": summary_payload["top_matched_hint_facets"],
                "top_fallback_benchmarks": summary_payload["top_fallback_benchmarks"],
                "top_fallback_reasons": summary_payload["top_fallback_reasons"],
                "top_fallback_selection_reasons": summary_payload["top_fallback_selection_reasons"],
                "top_fallback_benchmark_shares": summary_payload["top_fallback_benchmark_shares"],
                "fallback_concentration_warning": summary_payload["fallback_concentration_warning"],
            }
            for field, value in scalar_rows.items():
                if field == "top_fallback_benchmark_shares":
                    rendered = _format_share_rows(value, key="benchmark_id")
                elif field in {"top_fallback_reasons", "top_fallback_selection_reasons"}:
                    rendered = _format_count_rows(value, key="reason")
                else:
                    rendered = json.dumps(value, sort_keys=True) if isinstance(value, list) else str(value)
                summary_table.add_row(field, rendered)
            Console(width=200).print(summary_table)

        if calibration_report:
            calibration_table = Table(title="Gap Calibration", show_header=True, header_style="bold")
            calibration_table.add_column("field", overflow="fold", no_wrap=False)
            calibration_table.add_column("value", overflow="fold", no_wrap=False)
            for field, value in payload["calibration"].items():
                calibration_table.add_row(field, json.dumps(value, sort_keys=True))
            Console(width=200).print(calibration_table)

        if evidence_report:
            evidence_payload = payload["evidence_report"]
            evidence_rows = evidence_payload.get("entities", {}) if evidence_payload["enabled"] else {}
            evidence_table = Table(title="Gap Evidence", show_header=True, header_style="bold")
            for col in ("entity", "mode", "hints", "matched facets", "unmapped terms", "why"):
                evidence_table.add_column(col, overflow="fold", no_wrap=False)
            for entity_id, row in evidence_rows.items():
                evidence_table.add_row(
                    entity_id,
                    row["candidate_mode"],
                    ", ".join(row["facet_hints"]) or "-",
                    ", ".join(row["matched_facets"]) or "-",
                    ", ".join(row["unmapped_high_value_terms"][:8]) or "-",
                    ", ".join(row["why_no_specific_candidate"]) or "-",
                )
            Console(width=200).print(evidence_table)

    emit(output_format=output_format, payload=output_payload, render_text=_render, sort_keys=True)
