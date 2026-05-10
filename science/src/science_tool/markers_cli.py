"""Click CLI group for `science markers`."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import click

from science_tool.markers import LEGACY_ALIASES, scan_markers
from science_tool.markdown_utils import is_fence_line


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
def scan(root_path: Path, output_format: str, strict: bool, include_documentation: bool) -> None:
    """Scan project markdown for annotation tokens."""
    root = root_path.resolve()
    hits = scan_markers(root, strict=strict, include_documentation=include_documentation)
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
                    "legacy": h.legacy,
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
        legacy = " (legacy spelling)" if h.legacy else ""
        click.echo(f"  {rel}:{h.line}  [{h.token}]  {h.severity}{legacy}")


@markers_group.command("migrate")
@click.option(
    "--root",
    "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option("--write", is_flag=True, help="Apply rewrites in place (otherwise dry-run).")
def migrate(root_path: Path, write: bool) -> None:
    """Rewrite legacy token spellings to their canonical forms.

    Only bare-prose occurrences are rewritten. Backticked or fenced-code
    occurrences are left alone (they are documentation references to the
    legacy spelling, e.g., in this convention doc itself).
    """
    root = root_path.resolve()
    hits = scan_markers(root, strict=False)
    legacy_hits = [h for h in hits if h.legacy]
    if not legacy_hits:
        click.echo("markers migrate: no legacy tokens found")
        return

    by_file: dict[Path, list[int]] = {}
    for h in legacy_hits:
        by_file.setdefault(h.file, []).append(h.line)

    for path, lines in sorted(by_file.items()):
        rel = path.relative_to(root)
        click.echo(f"  {rel}: {len(lines)} legacy token(s) on lines {sorted(set(lines))}")
        if not write:
            continue
        _rewrite_legacy_tokens_in_file(path)

    if not write:
        click.echo()
        click.echo("Dry-run. Re-run with --write to apply.")


_INLINE_CODE_SPLIT_RE = re.compile(r"(`[^`]*`)")


def _rewrite_legacy_tokens_in_file(path: Path) -> None:
    """Rewrite bare-prose legacy tokens in `path` to their canonical spellings.

    Backticked / fenced-code occurrences are preserved verbatim.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    in_fenced = False
    out_lines: list[str] = []
    for line in lines:
        stripped_newline = line.rstrip("\n")
        if is_fence_line(stripped_newline):
            in_fenced = not in_fenced
            out_lines.append(line)
            continue
        if in_fenced:
            out_lines.append(line)
            continue
        out_lines.append(_rewrite_prose_legacy_tokens(line))
    path.write_text("".join(out_lines), encoding="utf-8")


def _rewrite_prose_legacy_tokens(line: str) -> str:
    parts = _INLINE_CODE_SPLIT_RE.split(line)
    for i, part in enumerate(parts):
        if part.startswith("`") and part.endswith("`"):
            continue  # preserve backticked content
        rewritten = part
        for legacy_inner, canonical in LEGACY_ALIASES.items():
            rewritten = rewritten.replace(f"[{legacy_inner}]", f"[{canonical}]")
        parts[i] = rewritten
    return "".join(parts)
