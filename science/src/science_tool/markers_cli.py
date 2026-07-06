"""Click CLI group for `science markers`."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import click

from science_tool.markers import scan_markers


@click.group("markers")
def markers_group() -> None:
    """Annotation-token tooling for Science projects."""


@markers_group.command("scan")
@click.option(
    "--root",
    "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(("table", "json")),
    default="table",
    show_default=True,
)
@click.option(
    "--strict",
    is_flag=True,
    help="Promote INFO-severity tokens (SPECULATION, INACCESSIBLE) to WARN.",
)
@click.option(
    "--include-documentation",
    is_flag=True,
    help="Include backticked / fenced-code occurrences (audit / migration).",
)
@click.option(
    "--ignore-lifted",
    is_flag=True,
    help="Skip hits already represented in a sibling .anno.trig sidecar.",
)
def scan(
    root_path: Path,
    output_format: str,
    strict: bool,
    include_documentation: bool,
    ignore_lifted: bool,
) -> None:
    """Scan project markdown for annotation tokens."""
    root = root_path.resolve()
    hits = scan_markers(root, strict=strict, include_documentation=include_documentation)
    if ignore_lifted:
        hits = _filter_lifted(hits)
    counts = Counter(h.token for h in hits)

    if output_format == "json":
        payload = {
            "counts": dict(counts),
            "hits": [
                {
                    "file": str(h.file.relative_to(root)),
                    "line": h.line,
                    "token": h.token,
                    "severity": h.severity,
                    "in_documentation": h.in_documentation,
                }
                for h in hits
            ],
        }
        click.echo(json.dumps(payload, indent=2))
        return

    if not hits:
        click.echo("markers scan: no annotation tokens found")
        return

    click.echo("Counts by token:")
    for token, count in sorted(counts.items()):
        click.echo(f"  {token}: {count}")
    click.echo()
    for h in hits:
        rel = h.file.relative_to(root)
        click.echo(f"  {rel}:{h.line}  [{h.token}]  {h.severity}")


def _filter_lifted(hits: list) -> list:
    """Drop hits whose enclosing sentence has a sidecar row marker-lifted."""
    from science_tool.annotation.io import read_sidecar  # noqa: PLC0415

    sidecar_cache: dict[Path, "object"] = {}

    def load(p: Path):
        if p in sidecar_cache:
            return sidecar_cache[p]
        try:
            sc = read_sidecar(p) if p.exists() else None
        except Exception as exc:
            click.echo(
                f"warning: could not parse {p}: {exc}", err=True,
            )
            sc = None
        sidecar_cache[p] = sc
        return sc

    out = []
    for hit in hits:
        sidecar_path = hit.file.with_suffix(".anno.trig")
        sc = load(sidecar_path)
        if sc is None:
            out.append(hit)
            continue
        if not _hit_is_lifted(hit, sc):
            out.append(hit)
    return out


def _hit_is_lifted(hit, sidecar) -> bool:
    """True if any sidecar annotation matches this hit by source + token + line."""
    from science_tool.annotation.selector import (  # noqa: PLC0415
        ResolutionStatus,
        resolve_selector,
    )

    literal = f"[{hit.token}]"
    try:
        source_text = hit.file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    line_offsets = [0]
    for i, ch in enumerate(source_text):
        if ch == "\n":
            line_offsets.append(i + 1)
    if hit.line < 1 or hit.line > len(line_offsets):
        return False
    line_start = line_offsets[hit.line - 1]
    line_end = line_offsets[hit.line] if hit.line < len(line_offsets) else len(source_text)

    for ann in sidecar.annotations:
        if ann.source != "marker-scanner:phase-2":
            continue
        if ann.lifted_from != literal:
            continue
        result = resolve_selector(source_text, ann.target.selector)
        if result.status == ResolutionStatus.SUPERSEDED:
            continue
        if result.start is None or result.end is None:
            continue
        # Containment: any character of the resolved range lies on hit.line.
        if result.start < line_end and result.end > line_start:
            return True
    return False
