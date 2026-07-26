"""`science datasets` command group — dataset discovery and download."""
from __future__ import annotations

from pathlib import Path

import click

from science_tool.data_root import (
    DataRootConfigError,
    discover_project_root,
    resolve_data_root,
)
from science_tool.data_worktree import hydrate_worktree_data
from science_tool.datasets import available_adapters, get_adapter, search_all
from science_tool.datasets import infer_schema as _infer_schema
from science_tool.datasets.validate import validate_path
from science_tool.output import OUTPUT_FORMATS, emit, emit_query_rows


@click.group("datasets")
def datasets_group() -> None:
    """Dataset discovery and download commands."""


@datasets_group.command("sources")
def datasets_sources() -> None:
    """List available dataset adapters."""
    adapters = available_adapters()
    if not adapters:
        click.echo("No dataset adapters available. Install with: uv add science[datasets]")
        return
    click.echo("Available dataset sources:")
    for name in adapters:
        click.echo(f"  - {name}")


@datasets_group.command("search")
@click.argument("query")
@click.option("--source", default=None, help="Comma-separated list of sources (e.g. zenodo,geo)")
@click.option("--max", "max_results", default=20, show_default=True, help="Max results per source")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def datasets_search(
    query: str, source: str | None, max_results: int, output_format: str, output_path: Path | None
) -> None:
    """Search for datasets across repositories."""
    sources = source.split(",") if source else None
    results = search_all(
        query,
        sources=sources,
        max_per_source=max_results,
        on_error=lambda name, exc: click.echo(f"Warning: source {name!r} unavailable: {exc}", err=True),
    )
    if not results:
        click.echo("No datasets found.")
        return

    rows = [
        {
            "source": r.source,
            "id": r.id,
            "title": r.title[:80],
            "year": r.year or "",
            "access": r.access or "",
            "modality": r.modality or "",
            "organism": r.organism or "",
            "sample_count": r.sample_count or "",
            "doi": r.doi or "",
        }
        for r in results
    ]

    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("datasets-search", output_format))
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("datasets search"), output_path=output_path, command_path="datasets search", complete_via=complete_via
    )
    emit_query_rows(
        output_format=output_format,
        title=f"Dataset Search: {query}",
        columns=[
            ("source", "Source"),
            ("id", "ID"),
            ("title", "Title", {"no_wrap": True}),
            ("year", "Year"),
            ("access", "Access"),
            ("modality", "Modality"),
            ("organism", "Organism"),
            ("doi", "DOI"),
        ],
        rows=rows,
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@datasets_group.command("metadata")
@click.argument("source_id", metavar="SOURCE:ID")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_metadata(source_id: str, output_format: str) -> None:
    """Show full metadata for a dataset. Use SOURCE:ID format (e.g. zenodo:12345)."""
    source, _, dataset_id = source_id.partition(":")
    if not dataset_id:
        raise click.ClickException("Use SOURCE:ID format, e.g. zenodo:12345 or geo:GSE12345")
    adapter = get_adapter(source)
    result = adapter.metadata(dataset_id)

    rows = [
        {"field": "Source", "value": result.source},
        {"field": "ID", "value": result.id},
        {"field": "Title", "value": result.title},
        {"field": "Description", "value": result.description[:200] if result.description else ""},
        {"field": "DOI", "value": result.doi or ""},
        {"field": "URL", "value": result.url or ""},
        {"field": "Year", "value": str(result.year) if result.year else ""},
        {"field": "License", "value": result.license or ""},
        {"field": "Access", "value": result.access or ""},
        {"field": "Keywords", "value": ", ".join(result.keywords) if result.keywords else ""},
        {"field": "Organism", "value": result.organism or ""},
        {"field": "Modality", "value": result.modality or ""},
        {"field": "Samples", "value": str(result.sample_count) if result.sample_count else ""},
        {"field": "Files", "value": str(result.file_count) if result.file_count else ""},
    ]

    emit_query_rows(
        output_format=output_format,
        title=f"Dataset: {result.title}",
        columns=[("field", "Field"), ("value", "Value")],
        rows=rows,
    )


@datasets_group.command("files")
@click.argument("source_id", metavar="SOURCE:ID")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def datasets_files(source_id: str, output_format: str, output_path: Path | None) -> None:
    """List downloadable files in a dataset. Use SOURCE:ID format."""
    source, _, dataset_id = source_id.partition(":")
    if not dataset_id:
        raise click.ClickException("Use SOURCE:ID format, e.g. zenodo:12345")
    adapter = get_adapter(source)
    file_list = adapter.files(dataset_id)
    if not file_list:
        click.echo("No files found.")
        return

    rows = [
        {
            "filename": f.filename,
            "format": f.format or "",
            "size": _human_size(f.size_bytes) if f.size_bytes else "",
            "checksum": (f.checksum[:30] + "...") if f.checksum and len(f.checksum) > 30 else (f.checksum or ""),
        }
        for f in file_list
    ]

    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("datasets-files", output_format))
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("datasets files"), output_path=output_path, command_path="datasets files", complete_via=complete_via
    )
    emit_query_rows(
        output_format=output_format,
        title="Files",
        columns=[("filename", "Filename"), ("format", "Format"), ("size", "Size"), ("checksum", "Checksum")],
        rows=rows,
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


def _resolve_cli_data_root(project_root: Path | None) -> Path:
    try:
        return resolve_data_root(discover_project_root(project_root))
    except DataRootConfigError as exc:
        raise click.ClickException(str(exc)) from exc


@datasets_group.command("download")
@click.argument("source_id", metavar="SOURCE:ID")
@click.option("--file", "file_pattern", default=None, help="Download only files matching this pattern")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path),
    help="Project root for resolving the configured data root.",
)
@click.option("--dest", "dest_dir", default=None, show_default="resolved data root / raw", type=click.Path(path_type=Path))
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def datasets_download(
    source_id: str,
    file_pattern: str | None,
    project_root: Path | None,
    dest_dir: Path | None,
    output_format: str,
    output_path: Path | None,
) -> None:
    """Download dataset files. Use SOURCE:ID format."""
    import fnmatch

    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_rows
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    source, _, dataset_id = source_id.partition(":")
    if not dataset_id:
        raise click.ClickException("Use SOURCE:ID format, e.g. zenodo:12345")
    if dest_dir is None:
        dest_dir = _resolve_cli_data_root(project_root) / "raw"
    adapter = get_adapter(source)
    file_list = adapter.files(dataset_id)

    sink = BoundedSink(
        lookup("datasets download"),
        output_path=output_path,
        command_path="datasets download",
        complete_via=build_complete_via(
            click.get_current_context(), output_hint=hint_for("datasets-download", output_format)
        ),
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete download report to {output_path}")
        if output_path is not None
        else None
    )

    if not file_list:

        def _render_no_files() -> None:
            sink.echo("No files found.")

        emit(output_format=output_format, payload={"downloaded": []}, render_text=_render_no_files, sink=sink)
        sink.flush()
        if control_notice is not None:
            click.echo(control_notice)
        return

    if file_pattern:
        file_list = [f for f in file_list if fnmatch.fnmatch(f.filename, file_pattern)]
        if not file_list:

            def _render_no_match() -> None:
                sink.echo(f"No files matching pattern: {file_pattern}")

            emit(
                output_format=output_format,
                payload={"downloaded": [], "pattern": file_pattern},
                render_text=_render_no_match,
                sink=sink,
            )
            sink.flush()
            if control_notice is not None:
                click.echo(control_notice)
            return

    downloaded: list[dict[str, str]] = []
    for fi in file_list:
        path = adapter.download(fi, dest_dir)
        downloaded.append({"filename": fi.filename, "path": str(path)})

    projected = project_rows(downloaded, sink.max_rows)
    displayed = projected.rows
    payload: dict[str, object] = {"downloaded": displayed}
    if projected.truncated:
        payload["truncation"] = {
            "omitted": projected.omitted,
            "total": projected.total,
            "complete_via": sink.complete_via,
        }

    def _render() -> None:
        for row in displayed:
            sink.echo(f"Downloading {row['filename']}...")
            sink.echo(f"  Saved to {row['path']}")
        if projected.truncated:
            sink.echo(f"showing {len(displayed)} of {projected.total} downloaded file(s)")
            sink.echo(f"  complete output:  {sink.complete_via}")

    emit(output_format=output_format, payload=payload, render_text=_render, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@datasets_group.command("validate")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path),
    help="Project root for resolving the configured data root.",
)
@click.option("--path", "data_path", default=None, show_default="resolved data root", type=click.Path(path_type=Path))
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def datasets_validate(
    project_root: Path | None, data_path: Path | None, output_format: str, output_path: Path | None
) -> None:
    """Validate Frictionless Data Packages in raw/ and processed/ directories."""
    if data_path is None:
        data_path = _resolve_cli_data_root(project_root)
    results = validate_path(data_path)

    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("datasets-validate", output_format))
    control_notice = (
        bounded_control_notice(f"wrote {len(results)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("datasets validate"), output_path=output_path, command_path="datasets validate", complete_via=complete_via
    )
    emit_query_rows(
        output_format=output_format,
        title="Data Validation",
        columns=[("check", "Check"), ("status", "Status"), ("details", "Details")],
        rows=results,
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
    if any(r["status"] == "fail" for r in results):
        raise click.exceptions.Exit(1)


@datasets_group.command("qa")
@click.argument("path", type=click.Path(path_type=Path))
@click.option("--resource", "resource", default=None, help="Restrict QA to one resource (default: all tabular).")
@click.option(
    "--report-dir",
    "report_dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Persist qa_report.{json,md} (+ per-resource subdirs). Default: print only.",
)
@click.option(
    "--config",
    "runknobs",
    default=None,
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    help="Optional operational run-knobs YAML overlaid on the schema-derived config.",
)
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", show_default=True)
@click.option("--no-strict", is_flag=True, default=False, help="Suppress the build-fatal exit 1 (local inspection).")
def datasets_qa(
    path: Path,
    resource: str | None,
    report_dir: Path | None,
    runknobs: Path | None,
    output_format: str,
    no_strict: bool,
) -> None:
    """Run schema-driven QA over a datapackage's tabular resources (package-level).

    Exit codes: 0 ok · 1 structural flag fired (build-fatal; --no-strict forces 0) ·
    2 bad input (missing descriptor / unknown resource / unreadable data).
    """
    from science_qa.compile import CompileError
    from science_qa.runner import RunnerError, package_report_dict

    from science_tool.datasets import qa as _qa

    try:
        result, code = _qa.run_package_qa(
            path, resource=resource, report_dir=report_dir, runknobs=runknobs, no_strict=no_strict
        )
    except (CompileError, RunnerError, ValueError, FileNotFoundError) as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(2) from exc

    def _render() -> None:
        for outcome in result.outcomes:
            if outcome.status == "not-applicable":
                continue
            click.echo(_qa.render_resource_line(outcome))
        click.echo(_qa.render_package_summary(result))

    emit(output_format=output_format, payload=package_report_dict(result), render_text=_render, sort_keys=True)

    if code:
        raise click.exceptions.Exit(code)


@datasets_group.command("infer-schema")
@click.argument("datapackage", type=click.Path(path_type=Path))
@click.option("--resource", "resource", required=True, help="Resource name (or path) to infer.")
@click.option("--sample", default=10000, show_default=True, help="Max rows sampled for inference.")
@click.option("--write", "do_write", is_flag=True, help="Apply ONLY the safe names+types patch in place.")
@click.option(
    "--emit-suggestions",
    "suggestions_path",
    default=None,
    type=click.Path(path_type=Path),
    help="Write the review report to this YAML file (never mutates the descriptor).",
)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_infer_schema(
    datapackage: Path,
    resource: str,
    sample: int,
    do_write: bool,
    suggestions_path: Path | None,
    output_format: str,
) -> None:
    """Infer a resource's observed shape (field names + coarse types) from its table.

    Read-only by default (prints a diff vs the existing schema + a review report). With
    --write, applies ONLY the safe names+types patch; it never infers constraints, keys,
    foreignKeys, or qa: those are recommended in the report and authored by hand. Writes
    are canonical (the descriptor is re-rendered in its own format; formatting/comments are
    not preserved).
    """
    try:
        result = _infer_schema.infer_schema_result(datapackage, resource, sample)
    except _infer_schema.InferSchemaError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        click.echo(_infer_schema.result_to_json(result), nl=False)
    else:
        emit_query_rows(
            output_format=output_format,
            title="Proposed schema (names + types only)",
            columns=[("glyph", ""), ("action", "Action"), ("field", "Field"), ("details", "Details")],
            rows=_infer_schema.render_diff_rows(result.diff),
        )
        emit_query_rows(
            output_format=output_format,
            title="Review recommendations (NOT applied — author by hand)",
            columns=[("kind", "Kind"), ("column", "Column"), ("note", "Note"), ("label", "Label")],
            rows=_infer_schema.render_report_rows(result.report),
        )

    if suggestions_path is not None:
        suggestions_path.write_text(_infer_schema.report_to_yaml(result.report), encoding="utf-8")
        click.echo(f"Wrote review report to {suggestions_path}")

    if do_write:
        try:
            _infer_schema.write_patch(result)
        except _infer_schema.InferSchemaError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"Applied names+types patch to {result.descriptor_path}")


@datasets_group.command("hydrate-worktree")
@click.option("--project-root", default=".", show_default=True, type=click.Path(path_type=Path))
@click.option(
    "--source-root",
    default=None,
    type=click.Path(path_type=Path),
    help="Checkout that already has ignored local data directories. Defaults to auto-detecting another git worktree.",
)
@click.option("--dry-run", is_flag=True, help="Report actions without creating symlinks.")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def datasets_hydrate_worktree(
    project_root: Path,
    source_root: Path | None,
    dry_run: bool,
    output_format: str,
) -> None:
    """Symlink ignored data directories from another checkout into this worktree."""
    try:
        actions = hydrate_worktree_data(project_root=project_root, source_root=source_root, dry_run=dry_run)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    rows = [
        {
            "path": action.relative_path.as_posix(),
            "status": action.status,
            "source": str(action.source),
            "target": str(action.target),
            "details": action.details,
        }
        for action in actions
    ]
    emit_query_rows(
        output_format=output_format,
        title="Data Worktree Hydration",
        columns=[
            ("path", "Path"),
            ("status", "Status"),
            ("source", "Source"),
            ("target", "Target"),
            ("details", "Details"),
        ],
        rows=rows,
    )
    if all(action.status == "missing-source" for action in actions):
        raise click.exceptions.Exit(1)


def _human_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"
