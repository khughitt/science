"""Project-overlay discovery and read-time merge for the commons store.

A project carries a thin overlay file (`<project>/doc/<type>/<slug>.md`) for a
commons entity. This module discovers, parses, and validates overlay files,
and merges them onto the canonical entity per the schema's `science:merge`
policy. Git `pin_version` resolution is deferred to Phase E; D1 parses the
field but the merge always uses the live canonical entity.

See docs/plans/2026-05-14-commons-overlay-merge-design.md.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.markdown_utils import parse_frontmatter


def _read_markdown_body(path: Path) -> str:
    """Return the markdown body of `path`: everything after the frontmatter."""
    _, body_start = parse_frontmatter(path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(lines[body_start - 1 :])
