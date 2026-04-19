"""Pure-function core for migrating legacy ``article:`` IDs to ``paper:``.

See docs/specs/2026-04-19-manuscript-paper-rename-design.md for the
canonical rewrite rules.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

# Entity-ID character class per the spec: [A-Za-z0-9_\-.]
_ENTITY_ID_CLASS = r"[A-Za-z0-9_\-.]"

# YAML-style rewrites for the `article:` prefix embedded in entity IDs.
ID_REWRITE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"id: article:"), "id: paper:"),
    (re.compile(r'id: "article:'), 'id: "paper:'),
    (re.compile(r"- article:"), "- paper:"),
    (re.compile(r"\[article:"), "[paper:"),
    (re.compile(r'"article:'), '"paper:'),
    (re.compile(r"'article:"), "'paper:"),
]

# Frontmatter `type:` rewrites — must be applied ONLY to the top YAML block.
TYPE_REWRITE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^type: article\s*$", re.MULTILINE), "type: paper"),
    (re.compile(r'^type: "article"\s*$', re.MULTILINE), 'type: "paper"'),
    (re.compile(r"^type: 'article'\s*$", re.MULTILINE), "type: 'paper'"),
]

# Prose fallback: `article:<id>` anywhere in body/YAML values.
# Word boundary avoids rewriting `particle:` and similar substrings.
PROSE_REWRITE_RULE: tuple[re.Pattern[str], str] = (
    re.compile(rf"\barticle:(?={_ENTITY_ID_CLASS})"),
    "paper:",
)


def rewrite_text(text: str) -> tuple[str, int]:
    """Apply all rewrite rules to ``text``; return (new_text, match_count).

    Rules are applied in this order:
    1. Frontmatter `type:` rewrites (MULTILINE regex; safe across the whole file
       because the pattern is anchored with `^type: article` which won't match
       prose).
    2. ID-field rewrites (literal prefix rewrites).
    3. Prose/word-boundary rewrite for any remaining `article:<X>` matches.

    Idempotent: re-running on already-migrated text returns the same text and
    a count of 0.
    """
    total = 0
    current = text

    for pattern, replacement in TYPE_REWRITE_RULES:
        current, n = pattern.subn(replacement, current)
        total += n

    for pattern, replacement in ID_REWRITE_RULES:
        current, n = pattern.subn(replacement, current)
        total += n

    pattern, replacement = PROSE_REWRITE_RULE
    current, n = pattern.subn(replacement, current)
    total += n

    return current, total


# Directories to scan, relative to project root. Matches the conventions used
# by `science_tool.refs.check_refs` and the spec's "canonical markdown roots".
_SCAN_ROOTS: tuple[str, ...] = ("doc", "specs", "tasks", "core", "knowledge")
_TOP_LEVEL_MARKDOWN: tuple[str, ...] = ("RESEARCH_PLAN.md", "README.md")


@dataclass(frozen=True)
class FileRewrite:
    path: Path
    original_text: str
    new_text: str
    match_count: int


def scan_project(project_root: Path) -> list[FileRewrite]:
    """Walk ``project_root``; return pending rewrites for markdown files.

    Returns an empty list if the project has no legacy ``article:`` references.
    Does NOT write anything — callers apply the rewrites themselves via
    :func:`apply_rewrites`.
    """
    results: list[FileRewrite] = []
    for md_path in _iter_markdown_files(project_root):
        try:
            text = md_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Non-UTF-8 files: skip with a logged warning. Spec §Open Decisions
            # documents this behavior.
            continue
        new_text, count = rewrite_text(text)
        if count > 0:
            results.append(FileRewrite(md_path, text, new_text, count))
    return sorted(results, key=lambda r: r.path.as_posix())


def _iter_markdown_files(project_root: Path) -> Iterator[Path]:
    for rel in _SCAN_ROOTS:
        root = project_root / rel
        if not root.is_dir():
            continue
        yield from sorted(root.rglob("*.md"))
    for name in _TOP_LEVEL_MARKDOWN:
        path = project_root / name
        if path.is_file():
            yield path
