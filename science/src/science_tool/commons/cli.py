"""Click CLI for `science commons`."""

from __future__ import annotations

import json
from pathlib import Path

import click

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.bootstrap import init_commons
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsError
from science_tool.commons.registry import RegistryBuilder


@click.group("commons")
def commons_group() -> None:
    """Manage the shared knowledge store."""


@commons_group.command("init")
@click.option("--force", is_flag=True, help="Initialize even if the path is non-empty.")
def init_cmd(force: bool) -> None:
    """Create or verify the commons store layout."""
    root = resolve_commons_root()
    try:
        init_commons(root, force=force)
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"commons initialized at {root}")


@commons_group.group("index")
def index_group() -> None:
    """Manage the commons registry index."""


@index_group.command("rebuild")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON report.")
def index_rebuild_cmd(as_json: bool) -> None:
    """Rebuild registry.sqlite from filesystem state."""
    root = _require_root()
    adapter = CommonsEntityAdapter(root)
    report = RegistryBuilder(root, adapter).rebuild()
    if as_json:
        payload = {
            "entities_indexed": report.entities_indexed,
            "errors": [
                {
                    "path": str(e.path),
                    "canonical_id": e.canonical_id,
                    "message": str(e.cause),
                }
                for e in report.errors
            ],
            "duration_ms": report.duration_ms,
        }
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        click.echo(f"indexed {report.entities_indexed} entities in {report.duration_ms} ms")
        for err in report.errors:
            click.echo(f"  error: {err}", err=True)
    if report.errors:
        raise click.exceptions.Exit(1)


def _require_root() -> Path:
    """Resolve the commons root, raising a ClickException if it is missing."""
    root = resolve_commons_root()
    if not root.is_dir():
        raise click.ClickException(
            f"commons store not found at {root}; run `science commons init`"
        )
    return root
