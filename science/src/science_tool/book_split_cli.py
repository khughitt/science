from __future__ import annotations

from pathlib import Path

import click

from science_tool.output import emit


@click.command("book-split")
@click.argument("pdf", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the chapter manifest as JSON.")
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted chapter manifest to PATH instead of stdout.",
)
def book_split_command(pdf: Path, output_format: str, as_json: bool, output_path: Path | None) -> None:
    """Extract a chapter manifest from a book PDF's outline/bookmarks.

    Intended for the /review-books command: call this first; on a non-zero exit
    with 'no outline', fall back to reading the book's table-of-contents pages.
    """
    from science_tool.book_split import BookSplitError, split_book
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_rows
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    try:
        chapters = split_book(pdf)
    except BookSplitError as exc:
        raise click.ClickException(str(exc)) from exc

    effective_format = "json" if (as_json or output_format == "json") else output_format
    sink = BoundedSink(
        lookup("book-split"),
        output_path=output_path,
        command_path="book-split",
        complete_via=build_complete_via(click.get_current_context(), output_hint=hint_for("book-split", effective_format)),
    )
    control_notice = (
        bounded_control_notice(f"wrote {len(chapters)} chapters to {output_path}")
        if output_path is not None
        else None
    )

    projected = project_rows(chapters, sink.max_rows)
    displayed = projected.rows
    payload: dict[str, object] = {"chapters": [c.to_dict() for c in displayed]}
    if projected.truncated:
        payload["truncation"] = {
            "omitted": projected.omitted,
            "total": projected.total,
            "complete_via": sink.complete_via,
        }

    def _render() -> None:
        for c in displayed:
            part = f"  [{c.part}]" if c.part else ""
            sink.echo(f"{c.n:>3}. {c.title}  (pp. {c.start_page}-{c.end_page}){part}")
        if projected.truncated:
            sink.echo(f"showing {len(displayed)} of {projected.total} chapters")
            sink.echo(f"  complete output:  {sink.complete_via}")

    emit(output_format=effective_format, payload=payload, render_text=_render, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
