"""`science bib` command group — project bibliography commands."""
from __future__ import annotations

from pathlib import Path

import click

from science_tool.output import OUTPUT_FORMATS, emit


@click.group("bib")
def bib_group() -> None:
    """Project bibliography (papers/references.bib) commands."""


@bib_group.command("add")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Project root containing papers/references.bib.",
)
@click.option("--entry", "entry", default=None, help="BibTeX entry text (inline).")
@click.option(
    "--entry-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Read the BibTeX entry from this file.",
)
@click.option("--replace", is_flag=True, help="Replace the existing entry if the key is already present.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def bib_add(
    project_root: Path,
    entry: str | None,
    entry_file: Path | None,
    replace: bool,
    output_format: str,
    as_json: bool,
) -> None:
    """Atomically append a BibTeX entry to papers/references.bib.

    Reads the entry from --entry, --entry-file, or stdin (in that order). A
    locked open-read-write cycle avoids the Read→Edit mtime race the Edit tool
    hits under Dropbox sync, and serializes concurrent appends from parallel
    subagents. Idempotent by key; pass --replace to overwrite an existing entry.

    Example (subagent heredoc):

        uv run science bib add --project-root . <<'EOF'
        @article{Smith2024, title={...}, author={...}, year={2024}}
        EOF
    """
    from science_tool.bibliography import add_bib_entry

    if entry is not None:
        text = entry
    elif entry_file is not None:
        text = entry_file.read_text(encoding="utf-8")
    else:
        text = click.get_text_stream("stdin").read()
    if not text.strip():
        raise click.ClickException("No BibTeX entry provided (pass --entry, --entry-file, or pipe via stdin).")

    try:
        result = add_bib_entry(project_root, text, replace=replace)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    effective_format = "json" if (as_json or output_format == "json") else output_format
    emit(
        output_format=effective_format,
        payload={"key": result.key, "action": result.action, "path": str(result.path)},
        render_text=lambda: click.echo(f"{result.action}: {result.key} ({result.path})"),
        indent=None,
    )
