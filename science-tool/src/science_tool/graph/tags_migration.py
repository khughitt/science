"""Migration script: rewrite legacy `tags:` into `related: [meta:<tag>, ...]`.

The parse-time merge that previously absorbed `tags:` into `related` was removed,
so this physical migration is now the only path to convert legacy `tags:` data
into materializable `related` refs. Without running it, `tags:` lines in
frontmatter or task markdown are silently dropped on parse (the `health` command
flags them).

Default conversion is `meta:<tag>` (intentional metadata, no KG materialization).
Pass `as_topic=True` (or `--as-topic` on the CLI) for projects where every tag
value has been verified as a real domain topic — that switches to `topic:<tag>`.

Preserves YAML formatting by rewriting only the `tags:` and `related:` lines.
Task files (tasks/active.md, tasks/done/*.md) are migrated with the same
surgical approach — each task block is treated like a mini-frontmatter with
`- field: value` lines. Unknown fields (e.g. custom `depends-on:`) and
surrounding content (headers, descriptions) are preserved verbatim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


_TAGS_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)tags:\s*\[(?P<body>[^\]]*)\]\s*$", re.MULTILINE)
_RELATED_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)related:\s*\[(?P<body>[^\]]*)\]\s*$", re.MULTILINE)
# Block-form `related:` — key on its own line followed by one or more `- "X"` item lines.
_RELATED_BLOCK_RE = re.compile(
    r"^(?P<indent>[ \t]*)related:[ \t]*\n(?P<items>(?:[ \t]+-[^\n]*(?:\n|$))+)",
    re.MULTILINE,
)
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)

# Task-file line patterns (dash-prefixed)
_TASK_HEADER_RE = re.compile(r"^## \[\w+\]", re.MULTILINE)
_TASK_TAGS_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)- tags:\s*\[(?P<body>[^\]]*)\]\s*$", re.MULTILINE)
_TASK_RELATED_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)- related:\s*\[(?P<body>[^\]]*)\]\s*$", re.MULTILINE)


@dataclass
class FileMigration:
    """Record of what would change (or did change) in one file."""

    path: Path
    tag_values: list[str] = field(default_factory=list)
    added_to_related: list[str] = field(default_factory=list)


@dataclass
class MigrationReport:
    """Summary of a tags→related migration run."""

    applied: bool
    entity_files: list[FileMigration] = field(default_factory=list)
    task_files: list[Path] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)


def _unquote(item: str) -> str:
    """Strip surrounding single or double quotes from a YAML list item."""
    s = item.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def _parse_list_body(body: str) -> list[str]:
    return [_unquote(item) for item in body.split(",") if item.strip()]


def _parse_block_items(items_text: str) -> list[str]:
    """Parse YAML block-list items (`  - "X"`, `  - Y`, etc.) into ref strings."""
    refs: list[str] = []
    for line in items_text.splitlines():
        stripped = line.lstrip(" \t")
        if not stripped.startswith("-"):
            continue
        value = stripped[1:].strip()
        if value:
            refs.append(_unquote(value))
    return refs


def _format_list_body(items: list[str]) -> str:
    return ", ".join(items)


def _tag_to_ref(tag: str, as_topic: bool = False) -> str:
    """Convert a bare tag value to a typed ref.

    Default is `meta:<tag>` — safe metadata that won't pollute the KG.
    Pass as_topic=True for projects where all tags are verified domain topics.
    """
    if ":" in tag:
        return tag  # Already typed
    return f"topic:{tag}" if as_topic else f"meta:{tag}"


def rewrite_frontmatter(text: str, as_topic: bool = False) -> tuple[str, FileMigration | None]:
    """Rewrite a file's YAML frontmatter to drop `tags:` and merge into `related:`.

    Returns (new_text, migration_record). migration_record is None if no change.
    """
    fm_match = _FRONTMATTER_RE.match(text)
    if fm_match is None:
        return text, None

    fm_text = fm_match.group(1)
    tag_match = _TAGS_LINE_RE.search(fm_text)
    if tag_match is None:
        return text, None

    tag_values = _parse_list_body(tag_match.group("body"))
    tag_refs = [_tag_to_ref(t, as_topic=as_topic) for t in tag_values]

    # Remove the tags: line (including trailing newline if present)
    tags_start, tags_end = tag_match.span()
    new_fm = fm_text[:tags_start] + fm_text[tags_end:]
    # Collapse the leading newline left behind (if the tags: line was not at the start)
    if tags_start > 0 and new_fm[tags_start - 1 : tags_start + 1] == "\n\n":
        new_fm = new_fm[:tags_start] + new_fm[tags_start + 1 :]

    added: list[str] = []
    if tag_refs:
        inline_match = _RELATED_LINE_RE.search(new_fm)
        block_match = _RELATED_BLOCK_RE.search(new_fm) if inline_match is None else None
        if inline_match is not None:
            existing = _parse_list_body(inline_match.group("body"))
            merged = list(existing)
            for ref in tag_refs:
                if ref not in merged:
                    merged.append(ref)
                    added.append(ref)
            if added:
                indent = inline_match.group("indent")
                replacement = f"{indent}related: [{_format_list_body(merged)}]"
                new_fm = new_fm[: inline_match.start()] + replacement + new_fm[inline_match.end() :]
        elif block_match is not None:
            items_text = block_match.group("items")
            existing = _parse_block_items(items_text)
            # Preserve the item indent from the first existing line (e.g. "  - ").
            first_item = items_text.splitlines()[0]
            item_indent = first_item[: len(first_item) - len(first_item.lstrip(" \t"))]
            for ref in tag_refs:
                if ref not in existing:
                    existing.append(ref)
                    added.append(ref)
            if added:
                # Ensure the block ends with a newline before appending new lines.
                trailing_nl = "" if items_text.endswith("\n") else "\n"
                added_lines = "".join(f'{item_indent}- "{ref}"\n' for ref in added)
                new_items = items_text + trailing_nl + added_lines
                new_fm = new_fm[: block_match.start("items")] + new_items + new_fm[block_match.end("items") :]
        else:
            # No related: line — append one
            indent_match = _TAGS_LINE_RE.search(fm_text)  # reuse original for indent
            indent = indent_match.group("indent") if indent_match else ""
            new_fm = new_fm.rstrip("\n") + "\n" + f"{indent}related: [{_format_list_body(tag_refs)}]"
            added = list(tag_refs)

    # Reassemble full file
    body_after_fm = text[fm_match.end() :]
    new_text = f"---\n{new_fm.rstrip()}\n---\n{body_after_fm}"

    return new_text, FileMigration(
        path=Path("<unknown>"),  # caller fills in
        tag_values=tag_values,
        added_to_related=added,
    )


def _migrate_entity_file(path: Path, apply: bool, as_topic: bool = False) -> FileMigration | None:
    """Migrate one entity markdown file. Returns a record if changes were made."""
    text = path.read_text(encoding="utf-8")
    new_text, migration = rewrite_frontmatter(text, as_topic=as_topic)
    if migration is None:
        return None
    migration.path = path
    if apply and new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return migration


def _rewrite_task_block(block: str, as_topic: bool = False) -> tuple[str, list[str]]:
    """Surgically rewrite one task block: drop `- tags: [...]`, merge values into `- related:`.

    Returns (new_block, added_refs). Preserves all other lines verbatim, including
    unknown fields (`- depends-on:` etc.), headers, and description body.
    """
    tag_match = _TASK_TAGS_LINE_RE.search(block)
    if tag_match is None:
        return block, []

    tag_values = _parse_list_body(tag_match.group("body"))
    tag_refs = [_tag_to_ref(t, as_topic=as_topic) for t in tag_values]

    tags_start, tags_end = tag_match.span()
    # Drop the `- tags: [...]` line and its trailing newline
    newline_end = tags_end + 1 if tags_end < len(block) and block[tags_end] == "\n" else tags_end
    new_block = block[:tags_start] + block[newline_end:]

    added: list[str] = []
    if tag_refs:
        related_match = _TASK_RELATED_LINE_RE.search(new_block)
        if related_match is not None:
            existing = _parse_list_body(related_match.group("body"))
            merged = list(existing)
            for ref in tag_refs:
                if ref not in merged:
                    merged.append(ref)
                    added.append(ref)
            if added:
                indent = related_match.group("indent")
                replacement = f"{indent}- related: [{_format_list_body(merged)}]"
                new_block = new_block[: related_match.start()] + replacement + new_block[related_match.end() :]
        else:
            # No related: line — insert one where the tags: line was
            indent = tag_match.group("indent")
            insert_line = f"{indent}- related: [{_format_list_body(tag_refs)}]\n"
            new_block = new_block[:tags_start] + insert_line + new_block[tags_start:]
            added = list(tag_refs)

    return new_block, added


def rewrite_task_file(text: str, as_topic: bool = False) -> tuple[str, list[list[str]]]:
    """Rewrite a task markdown file: migrate each task block's `- tags:` into `- related:`.

    Returns (new_text, per_block_added_refs). per_block_added_refs is a list of
    added-refs lists (one entry per task block that changed).
    """
    # Find all task block boundaries
    headers = list(_TASK_HEADER_RE.finditer(text))
    if not headers:
        # No task headers; try treating the whole file as one block (may be a partial file)
        new_block, added = _rewrite_task_block(text, as_topic=as_topic)
        if added or new_block != text:
            return new_block, [added]
        return text, []

    # Build output: preamble (before first header) + each block rewritten
    parts: list[str] = [text[: headers[0].start()]]
    per_block_added: list[list[str]] = []

    for i, hdr in enumerate(headers):
        start = hdr.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end]
        new_block, added = _rewrite_task_block(block, as_topic=as_topic)
        parts.append(new_block)
        if added or new_block != block:
            per_block_added.append(added)

    return "".join(parts), per_block_added


def _migrate_task_file(path: Path, apply: bool, as_topic: bool = False) -> bool:
    """Migrate one task markdown file surgically. Returns True if changes would be made."""
    text = path.read_text(encoding="utf-8")
    new_text, _ = rewrite_task_file(text, as_topic=as_topic)
    if new_text == text:
        return False
    if apply:
        path.write_text(new_text, encoding="utf-8")
    return True


def migrate_tags_to_related(project_root: Path, apply: bool = False, as_topic: bool = False) -> MigrationReport:
    """Walk a project and rewrite legacy `tags:` frontmatter into `related:` refs.

    Args:
        project_root: Project directory (typically contains science.yaml, doc/, tasks/).
        apply: If True, write changes to disk. If False, just report what would change.
        as_topic: If True, convert bare tags to `topic:<tag>` refs (legacy behavior).
            Default (False) uses `meta:<tag>` — safe metadata that won't pollute the KG.

    Returns:
        MigrationReport summarizing files that were (or would be) changed.
    """
    report = MigrationReport(applied=apply)
    project_root = project_root.resolve()

    for scan_dir in ["doc", "specs"]:
        base = project_root / scan_dir
        if not base.is_dir():
            continue
        for md_file in sorted(base.rglob("*.md")):
            try:
                migration = _migrate_entity_file(md_file, apply, as_topic=as_topic)
                if migration is not None:
                    report.entity_files.append(migration)
            except Exception as exc:  # noqa: BLE001
                report.errors.append((md_file, str(exc)))

    tasks_dir = project_root / "tasks"
    candidate_task_files: list[Path] = []
    if (tasks_dir / "active.md").is_file():
        candidate_task_files.append(tasks_dir / "active.md")
    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        candidate_task_files.extend(sorted(done_dir.glob("*.md")))

    for task_file in candidate_task_files:
        try:
            if _migrate_task_file(task_file, apply, as_topic=as_topic):
                report.task_files.append(task_file)
        except Exception as exc:  # noqa: BLE001
            report.errors.append((task_file, str(exc)))

    return report
