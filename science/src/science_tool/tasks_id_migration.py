"""Bulk migration helpers for invalid or stale task identifiers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class TaskIdMigrationError(ValueError):
    """Raised when a requested task-id migration is unsafe."""


@dataclass(frozen=True)
class TaskIdMigrationResult:
    changed_files: int
    renamed_paths: int
    scanned_files: int
    dry_run: bool


_OLD_TASK_ID_RE = re.compile(r"^t[0-9]{3,}[a-z]+$")
_NEW_TASK_ID_RE = re.compile(r"^t[0-9]{3,}$")
_TASK_HEADER_RE = re.compile(r"^##\s+\[([^\]]+)\]\s+")
_TASK_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])t[0-9]{3,}[a-z]+(?![A-Za-z0-9])")
_SLASH_SERIES_RE = re.compile(r"(?<![A-Za-z0-9])t[0-9]{3,}[a-z](?:/[a-z])+(?![A-Za-z0-9])")
_DASH_SERIES_RE = re.compile(r"(?<![A-Za-z0-9])t[0-9]{3,}[a-z][-\u2013\u2014][a-z](?![A-Za-z0-9])")
_TOKEN_PART_RE = re.compile(r"^(t[0-9]{3,})([a-z]+)$")

_EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".snakemake",
    ".venv",
    ".worktrees",
    "__pycache__",
    "archive",
    "data",
    "logs",
    "models",
    "node_modules",
    "results",
}
_GENERATED_PATH_PARTS = {"knowledge"}


def parse_task_id_mapping(raw_mappings: list[str] | tuple[str, ...]) -> dict[str, str]:
    mappings: dict[str, str] = {}
    reverse: dict[str, str] = {}
    for raw in raw_mappings:
        if "=" not in raw:
            raise TaskIdMigrationError(f"mapping must be OLD=NEW, got {raw!r}")
        old, new = (part.strip() for part in raw.split("=", 1))
        if not _OLD_TASK_ID_RE.match(old):
            raise TaskIdMigrationError(f"old task id {old!r} must be suffixed, like t001b")
        if not _NEW_TASK_ID_RE.match(new):
            raise TaskIdMigrationError(f"new task id {new!r} must match tNNN")
        if old in mappings:
            raise TaskIdMigrationError(f"duplicate old task id {old}")
        if new in reverse:
            raise TaskIdMigrationError(f"new task id {new} is assigned to both {reverse[new]} and {old}")
        mappings[old] = new
        reverse[new] = old
    if not mappings:
        raise TaskIdMigrationError("at least one --map OLD=NEW mapping is required")
    return mappings


def migrate_task_ids(
    project_root: Path,
    mappings: dict[str, str],
    *,
    parent_ref: str | None = None,
    include_generated: bool = False,
    apply: bool = False,
) -> TaskIdMigrationResult:
    """Rewrite task-id tokens and matching path names under ``project_root``."""
    root = project_root.resolve()
    _validate_mapping_ids(mappings)
    _validate_no_new_id_collisions(root, mappings, include_generated=include_generated)

    files = list(_iter_text_candidate_files(root, include_generated=include_generated))
    changed_files = 0
    for path in files:
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rewritten = replace_task_id_tokens(original, mappings)
        if parent_ref:
            rewritten = add_parent_to_migrated_task_blocks(rewritten, set(mappings.values()), parent_ref)
        if rewritten != original:
            changed_files += 1
            if apply:
                path.write_text(rewritten, encoding="utf-8")

    renamed_paths = _rename_paths(root, mappings, include_generated=include_generated, apply=apply)
    return TaskIdMigrationResult(
        changed_files=changed_files,
        renamed_paths=renamed_paths,
        scanned_files=len(files),
        dry_run=not apply,
    )


def replace_task_id_tokens(text: str, mappings: dict[str, str]) -> str:
    text = _SLASH_SERIES_RE.sub(lambda match: _replace_series(match.group(0), mappings, separator="/"), text)
    text = _DASH_SERIES_RE.sub(lambda match: _replace_dash_series(match.group(0), mappings), text)
    return _TASK_TOKEN_RE.sub(lambda match: _replace_token(match.group(0), mappings), text)


def add_parent_to_migrated_task_blocks(text: str, migrated_ids: set[str], parent_ref: str) -> str:
    if not migrated_ids:
        return text

    had_trailing_newline = text.endswith("\n")
    lines = text.splitlines()
    out: list[str] = []
    index = 0
    while index < len(lines):
        header = _TASK_HEADER_RE.match(lines[index])
        if header is None or header.group(1) not in migrated_ids:
            out.append(lines[index])
            index += 1
            continue

        block_start = index
        index += 1
        while index < len(lines) and _TASK_HEADER_RE.match(lines[index]) is None:
            index += 1
        block = lines[block_start:index]
        out.extend(_add_parent_to_block(block, parent_ref))

    rendered = "\n".join(out)
    if had_trailing_newline:
        rendered += "\n"
    return rendered


def _validate_mapping_ids(mappings: dict[str, str]) -> None:
    for old, new in mappings.items():
        if not _OLD_TASK_ID_RE.match(old):
            raise TaskIdMigrationError(f"old task id {old!r} must be suffixed, like t001b")
        if not _NEW_TASK_ID_RE.match(new):
            raise TaskIdMigrationError(f"new task id {new!r} must match tNNN")


def _validate_no_new_id_collisions(root: Path, mappings: dict[str, str], *, include_generated: bool) -> None:
    old_ids = set(mappings)
    new_ids = set(mappings.values())
    for path in _iter_text_candidate_files(root, include_generated=include_generated):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line in text.splitlines():
            match = _TASK_HEADER_RE.match(line)
            if match is None:
                continue
            task_id = match.group(1)
            if task_id in new_ids and task_id not in old_ids:
                rel = path.relative_to(root)
                raise TaskIdMigrationError(f"new task id {task_id} already exists in {rel}")


def _iter_text_candidate_files(root: Path, *, include_generated: bool) -> list[Path]:
    return [path for path in _walk_candidate_paths(root, include_generated=include_generated) if path.is_file()]


def _rename_paths(root: Path, mappings: dict[str, str], *, include_generated: bool, apply: bool) -> int:
    paths = list(_walk_candidate_paths(root, include_generated=include_generated))
    renamed = 0
    for path in sorted(paths, key=lambda item: len(item.parts), reverse=True):
        new_name = replace_task_id_tokens(path.name, mappings)
        if new_name == path.name:
            continue
        target = path.with_name(new_name)
        if target.exists() and target != path:
            rel = path.relative_to(root)
            target_rel = target.relative_to(root)
            raise TaskIdMigrationError(f"cannot rename {rel} to {target_rel}: target exists")
        renamed += 1
        if apply:
            path.rename(target)
    return renamed


def _walk_candidate_paths(root: Path, *, include_generated: bool) -> list[Path]:
    candidates: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = list(current.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_symlink():
                continue
            rel_parts = child.relative_to(root).parts
            if any(part in _EXCLUDED_DIRS for part in rel_parts):
                continue
            if not include_generated and any(part in _GENERATED_PATH_PARTS for part in rel_parts):
                continue
            candidates.append(child)
            if child.is_dir():
                stack.append(child)
    return candidates


def _replace_series(token: str, mappings: dict[str, str], *, separator: str) -> str:
    first, *suffixes = token.split(separator)
    parsed = _TOKEN_PART_RE.match(first)
    if parsed is None or len(parsed.group(2)) != 1:
        return token
    base = parsed.group(1)
    old_ids = [first, *(f"{base}{suffix}" for suffix in suffixes)]
    if not all(old_id in mappings for old_id in old_ids):
        return token
    return separator.join(mappings[old_id] for old_id in old_ids)


def _replace_dash_series(token: str, mappings: dict[str, str]) -> str:
    match = re.match(r"^(t[0-9]{3,})([a-z])[-\u2013\u2014]([a-z])$", token)
    if match is None:
        return token
    base, start, end = match.groups()
    if ord(end) < ord(start):
        return token
    old_ids = [f"{base}{chr(code)}" for code in range(ord(start), ord(end) + 1)]
    if not all(old_id in mappings for old_id in old_ids):
        return token
    return "-".join(mappings[old_id] for old_id in old_ids)


def _replace_token(token: str, mappings: dict[str, str]) -> str:
    if token in mappings:
        return mappings[token]

    parsed = _TOKEN_PART_RE.match(token)
    if parsed is None:
        return token
    base, suffixes = parsed.groups()
    if len(suffixes) <= 1:
        return token
    old_ids = [f"{base}{suffix}" for suffix in suffixes]
    if not all(old_id in mappings for old_id in old_ids):
        return token
    return "-".join(mappings[old_id] for old_id in old_ids)


def _add_parent_to_block(block: list[str], parent_ref: str) -> list[str]:
    if any(line.startswith("- parent:") for line in block[1:]):
        return block

    insert_at = 1
    for index, line in enumerate(block[1:], start=1):
        if not line.startswith("- "):
            break
        insert_at = index + 1
        if line.startswith("- status:"):
            insert_at = index + 1
            break
    return [*block[:insert_at], f"- parent: {parent_ref}", *block[insert_at:]]
