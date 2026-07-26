"""`science project` command group — project-level commands."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from science_tool.entities import list_entities
from science_tool.output import OUTPUT_FORMATS, emit, emit_query_rows
from science_tool.project_artifacts.cli import artifacts_group as _artifacts_group


@click.group("project")
def project_group() -> None:
    """Project-level commands."""


project_group.add_command(_artifacts_group)


@project_group.command("topic-coverage")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    envvar="SCIENCE_PROJECT_ROOT",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root containing entities/topics/.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def project_topic_coverage(project_root: Path, output_format: str) -> None:
    """Report how much of entities/topics/ is curated (substantive vs. stub)."""
    from science_tool.topic_coverage import MalformedTopicError, compute_topic_coverage

    try:
        cov = compute_topic_coverage(project_root)
    except MalformedTopicError as exc:
        raise click.ClickException(str(exc)) from exc

    def _render() -> None:
        if cov.n_topics == 0:
            click.echo("topics: 0 (no topics)")
            return
        warn = "  ⚠ stub-dominated" if cov.stub_dominated else ""
        click.echo(
            f"topics: {cov.n_topics} (substantive {cov.n_substantive}, "
            f"stubs {cov.n_topics - cov.n_substantive}) — stub_ratio {cov.stub_ratio:.2f}{warn}"
        )
        if cov.stub_dominated:
            for r in cov.topics:
                if not r.substantive:
                    click.echo(f"  stub: {r.id}")

    emit(output_format=output_format, payload=cov.to_dict(), render_text=_render)


@project_group.command("resolve-refs")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    envvar="SCIENCE_PROJECT_ROOT",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root whose question/hypothesis index refs resolve against.",
)
@click.option(
    "--query",
    "queries",
    multiple=True,
    required=True,
    help="Ref to resolve (repeatable): an id, slug, or keyword/title fragment.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def project_resolve_refs(project_root: Path, queries: tuple[str, ...], output_format: str) -> None:
    """Resolve free-string refs to canonical entity ids (id-slug + title matching)."""
    from science_tool.resolve_refs import build_ref_index, load_index_rows

    index = build_ref_index(load_index_rows(project_root))
    results = [index.resolve(q) for q in queries]

    def _render() -> None:
        for r in results:
            if r.resolved is not None:
                click.echo(f"{r.query} -> {r.resolved} ({r.match_kind})")
            elif r.candidates:
                click.echo(f"{r.query} -> {r.match_kind}: {', '.join(r.candidates)}")
            else:
                click.echo(f"{r.query} -> unresolved")

    emit(output_format=output_format, payload=[r.to_dict() for r in results], render_text=_render)


@project_group.command("serialize")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    envvar="SCIENCE_PROJECT_ROOT",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root containing science.yaml.",
)
@click.option(
    "--out",
    "out_archive",
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
    help="Output .tar.gz path (must be outside the project root).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Build despite data-audit boundary violations (audit only; "
    "never bypasses missing/untracked science.yaml or guard failures).",
)
def project_serialize(project_root: Path, out_archive: Path, force: bool) -> None:
    """Serialize the tracked project source into a deterministic, shareable bundle.

    Reproducibility, not a privacy scrubber: ships all git-tracked entities and
    results faithfully; restricted material must not be tracked.
    """
    from science_tool.project_package.serialize import SerializeError, serialize_project

    try:
        result = serialize_project(project_root, out_archive, force=force)
    except SerializeError as exc:
        raise click.ClickException(str(exc)) from exc
    suffix = " [forced]" if result.forced else ""
    click.echo(f"Serialized {result.file_count} file(s), {result.payload_count} payload(s){suffix} → {result.out_path}")


@project_group.command("verify")
@click.argument("bundle", type=click.Path(exists=False, dir_okay=False, path_type=Path))
@click.option(
    "--against",
    "against_root",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Compare the bundle to a live checkout (commit, source, payloads). Explicit only.",
)
@click.option(
    "--extract",
    "extract_to",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Materialize the bundle's source tree into this empty or new directory.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit a JSON verdict.")
@click.pass_context
def project_verify(
    ctx: click.Context,
    bundle: Path,
    against_root: Path | None,
    extract_to: Path | None,
    output_format: str,
    as_json: bool,
) -> None:
    """Verify a serialized project bundle."""
    from science_tool.project_package.verify import (
        BundleIntegrityError,
        VerifyError,
        verdict_json,
        verify_project,
    )

    emit_json = as_json or output_format == "json"

    try:
        result = verify_project(bundle, against=against_root, extract=extract_to)
    except BundleIntegrityError as exc:
        _emit_verify_error(emit_json, exit_code=2, status="integrity", message=str(exc))
        ctx.exit(2)
    except VerifyError as exc:
        _emit_verify_error(emit_json, exit_code=4, status="operational", message=str(exc))
        ctx.exit(4)

    def _render() -> None:
        _render_verify_human(result)
        for warning in result.warnings:
            click.echo(f"warning: {warning}", err=True)

    emit(
        output_format="json" if emit_json else output_format,
        payload=verdict_json(result),
        render_text=_render,
        sort_keys=True,
    )
    ctx.exit(result.exit_code)


def _emit_verify_error(as_json: bool, *, exit_code: int, status: str, message: str) -> None:
    emit(
        output_format="json" if as_json else "text",
        payload={"version": 1, "exit_code": exit_code, "status": status, "error": message},
        render_text=lambda: click.echo(f"error: {message}", err=True),
        sort_keys=True,
    )


def _render_verify_human(result: Any) -> None:
    click.echo(f"  OK schema {result.bundle_schema_version}")
    click.echo(f"  OK {result.file_count} file(s) match manifest hashes")
    click.echo(f"  OK data_version {result.data_version} recomputes")
    if result.extracted_to is not None:
        click.echo(f"  OK extracted -> {result.extracted_to}")

    against = result.against
    if against is not None:
        click.echo(f"\n  against: {against.root}")
        mark = "OK" if against.commit.match else "DIFFER"
        click.echo(f"    commit:   {against.commit.bundle[:8]} vs {against.commit.head[:8]}  {mark}")
        click.echo(
            f"    source:   {against.source.match}/{against.source.total} match"
            f"  (differ {len(against.source.differ)}, absent {len(against.source.absent)})"
        )
        click.echo(
            f"    payloads: {against.payloads.ok} ok, {len(against.payloads.differ)} differ, "
            f"{len(against.payloads.missing)} missing, {len(against.payloads.extra)} extra"
        )
        for path in against.payloads.missing:
            click.echo(f"              MISSING: {path}")
        for path in against.payloads.differ:
            click.echo(f"              DIFFER:  {path}")

    click.echo(f"\n  status: {result.status} (exit {result.exit_code})")


@project_group.command("index")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def project_index(output_format: str, project_root: Path, output_path: Path | None) -> None:
    """Produce a compact index of questions and hypotheses for this project."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    project_root = project_root.resolve()

    # Resolve entities through the canonical project-sources loader.
    rows: list[dict[str, str]] = []
    for kind in ("hypothesis", "question"):
        for entity in list_entities(project_root, kind=kind):
            rows.append(
                {
                    "kind": str(entity["kind"]),
                    "id": str(entity["id"]),
                    "file": str(entity["path"]),
                    "title": str(entity["title"]),
                    "status": str(entity["status"]),
                }
            )

    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("project-index", output_format))
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )
    sink = BoundedSink(
        lookup("project index"), output_path=output_path, command_path="project index", complete_via=complete_via
    )
    emit_query_rows(
        output_format=output_format,
        title="Project Index",
        columns=[
            ("kind", "Kind"),
            ("id", "ID"),
            ("file", "File"),
            ("title", "Title"),
            ("status", "Status"),
        ],
        rows=rows,
        sink=sink,
    )
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
