"""Migration script: rewrite legacy `tags:` frontmatter into `related: [topic:<tag>, ...]`.

The frontmatter parser already merges legacy tags into `related` at parse time
(science_model.frontmatter.parse_entity_file), so the system works without this
migration. This script physically rewrites the on-disk files so that `tags:`
disappears from frontmatter entirely and tag values become typed entity refs
in `related`.

Preserves YAML formatting by rewriting only the `tags:` and `related:` lines.
Task files (tasks/active.md, tasks/done/*.md) are migrated by reading through
the task parser (which does the merge) and re-rendering.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from science_tool.tasks import parse_tasks, render_tasks

_TAGS_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)tags:\s*\[(?P<body>[^\]]*)\]\s*$", re.MULTILINE)
_RELATED_LINE_RE = re.compile(r"^(?P<indent>[ \t]*)related:\s*\[(?P<body>[^\]]*)\]\s*$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)


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


def _format_list_body(items: list[str]) -> str:
    return ", ".join(items)


def _tag_to_ref(tag: str) -> str:
    return tag if ":" in tag else f"topic:{tag}"


def rewrite_frontmatter(text: str) -> tuple[str, FileMigration | None]:
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
    tag_refs = [_tag_to_ref(t) for t in tag_values]

    # Remove the tags: line (including trailing newline if present)
    tags_start, tags_end = tag_match.span()
    new_fm = fm_text[:tags_start] + fm_text[tags_end:]
    # Collapse the leading newline left behind (if the tags: line was not at the start)
    if tags_start > 0 and new_fm[tags_start - 1 : tags_start + 1] == "\n\n":
        new_fm = new_fm[: tags_start] + new_fm[tags_start + 1 :]

    added: list[str] = []
    if tag_refs:
        related_match = _RELATED_LINE_RE.search(new_fm)
        if related_match is not None:
            existing = _parse_list_body(related_match.group("body"))
            merged = list(existing)
            for ref in tag_refs:
                if ref not in merged:
                    merged.append(ref)
                    added.append(ref)
            if added:
                indent = related_match.group("indent")
                replacement = f"{indent}related: [{_format_list_body(merged)}]"
                new_fm = (
                    new_fm[: related_match.start()] + replacement + new_fm[related_match.end() :]
                )
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


def _migrate_entity_file(path: Path, apply: bool) -> FileMigration | None:
    """Migrate one entity markdown file. Returns a record if changes were made."""
    text = path.read_text(encoding="utf-8")
    new_text, migration = rewrite_frontmatter(text)
    if migration is None:
        return None
    migration.path = path
    if apply and new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return migration


def _migrate_task_file(path: Path, apply: bool) -> bool:
    """Migrate one task markdown file by round-tripping through the parser.

    The task parser already merges legacy `- tags: [...]` into `related` (Task 5
    of the tags→related unification). Reading and re-rendering is sufficient.

    Returns True if the file's contents would change.
    """
    tasks = parse_tasks(path)
    if not tasks:
        return False
    rendered = render_tasks(tasks)
    original = path.read_text(encoding="utf-8")
    if rendered == original:
        return False
    if apply:
        path.write_text(rendered, encoding="utf-8")
    return True


def migrate_tags_to_related(project_root: Path, apply: bool = False) -> MigrationReport:
    """Walk a project and rewrite legacy `tags:` frontmatter into `related:` refs.

    Args:
        project_root: Project directory (typically contains science.yaml, doc/, tasks/).
        apply: If True, write changes to disk. If False, just report what would change.

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
                migration = _migrate_entity_file(md_file, apply)
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
            if _migrate_task_file(task_file, apply):
                report.task_files.append(task_file)
        except Exception as exc:  # noqa: BLE001
            report.errors.append((task_file, str(exc)))

    return report
