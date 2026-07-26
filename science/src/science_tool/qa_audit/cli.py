from __future__ import annotations

from pathlib import Path

import click

from science_tool.output import emit
from science_tool.qa_audit.audit import audit_workflows, render_markdown


@click.command("qa-audit")
@click.option("--runs-dir", type=click.Path(path_type=Path), default=Path("entities/workflow-runs"),
              show_default=True, help="Directory of authored workflow-run entities.")
@click.option("--repo-root", type=click.Path(path_type=Path), default=Path("."), show_default=True,
              help="Repo root used to resolve each run's manifest_path.")
@click.option(
    "--out",
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted report to PATH instead of stdout (--out is a kept alias).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON rows instead of a table.")
def qa_audit_command(
    runs_dir: Path,
    repo_root: Path,
    output_path: Path | None,
    output_format: str,
    as_json: bool,
) -> None:
    """Advisory process-quality audit: flag single-run / QA-ignoring workflows.

    Always exits 0 — this never gates a build or `science validate`.
    """
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_rows
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    if not runs_dir.exists():
        raise click.ClickException(f"runs dir not found: {runs_dir}")
    rows = audit_workflows(runs_dir=runs_dir, repo_root=repo_root)

    effective_format = "json" if (as_json or output_format == "json") else output_format
    sink = BoundedSink(
        lookup("qa-audit"),
        output_path=output_path,
        command_path="qa-audit",
        complete_via=build_complete_via(click.get_current_context(), output_hint=hint_for("qa-audit", effective_format)),
    )
    control_notice = (
        bounded_control_notice(f"wrote {len(rows)} rows to {output_path}") if output_path is not None else None
    )

    projected = project_rows(rows, sink.max_rows)
    displayed_rows = projected.rows
    payload: dict[str, object] = {"rows": displayed_rows}
    if projected.truncated:
        payload["truncation"] = {
            "omitted": projected.omitted,
            "total": projected.total,
            "complete_via": sink.complete_via,
        }

    def _render() -> None:
        md = render_markdown(displayed_rows)
        sink.write(md)
        if projected.truncated:
            sink.echo(f"showing {len(displayed_rows)} of {projected.total} rows")
            sink.echo(f"  complete output:  {sink.complete_via}")

    emit(output_format=effective_format, payload=payload, render_text=_render, sink=sink, sort_keys=True)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
