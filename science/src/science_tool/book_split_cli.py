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
def book_split_command(pdf: Path, output_format: str, as_json: bool) -> None:
    """Extract a chapter manifest from a book PDF's outline/bookmarks.

    Intended for the /review-books command: call this first; on a non-zero exit
    with 'no outline', fall back to reading the book's table-of-contents pages.
    """
    from science_tool.book_split import BookSplitError, split_book

    try:
        chapters = split_book(pdf)
    except BookSplitError as exc:
        raise click.ClickException(str(exc)) from exc

    payload = [c.to_dict() for c in chapters]

    def _render() -> None:
        for c in chapters:
            part = f"  [{c.part}]" if c.part else ""
            click.echo(f"{c.n:>3}. {c.title}  (pp. {c.start_page}-{c.end_page}){part}")

    effective_format = "json" if (as_json or output_format == "json") else output_format
    emit(output_format=effective_format, payload=payload, render_text=_render)
