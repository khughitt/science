"""Build a `ChangeSet` from a recorded `base..head` commit range.

The range is two-dot (tree to tree) by construction. A merge-base range moves under
rebase and under integration-branch advancement, which is exactly the baseline
instability design §6 rejects -- so `...` must never appear here.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

import yaml
from science_model.frontmatter import split_frontmatter
from yaml.nodes import MappingNode, Node, ScalarNode

from science_tool.autonomy.changes import (
    BODY_FIELD,
    ChangeSet,
    ChangeType,
    PathChange,
    UNACCOUNTED_CHANGE_FIELD,
    entity_kind_for_path,
)

_STATUS_TO_CHANGE_TYPE = {"A": ChangeType.ADDED, "D": ChangeType.DELETED, "M": ChangeType.MODIFIED}


class ExtractError(ValueError):
    """The commit range could not be read.

    Never degrade this to an empty change set: an unreadable range is uncomputable,
    not clean.
    """


def _git(repo_root: Path, *args: str) -> bytes:
    """Run one git command with replacement objects disabled.

    `--no-replace-objects` prevents repository-local replacement refs from making a
    changed commit appear to have the same tree as its base.
    """
    try:
        result = subprocess.run(
            ["git", "--no-replace-objects", "-C", str(repo_root), *args], capture_output=True
        )
    except (OSError, ValueError) as exc:
        raise ExtractError(f"could not execute git {' '.join(args)} in {repo_root}: {exc}") from exc
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise ExtractError(f"git {' '.join(args)} failed in {repo_root}: {message}")
    return result.stdout


def _require_commit(repo_root: Path, rev: str) -> str:
    return _git(
        repo_root, "rev-parse", "--verify", "--end-of-options", f"{rev}^{{commit}}"
    ).decode().strip()


def _blob(repo_root: Path, commit: str, path: str) -> str:
    """Return a UTF-8 file blob at a commit, failing closed on unreadable input."""
    raw = _git(repo_root, "show", f"{commit}:{path}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractError(f"{path} at {commit} is not utf-8 text: {exc}") from exc


_MISSING = object()


def _same_value(before: object, after: object) -> bool:
    """Compare YAML values without Python's bool-is-an-int equivalence."""
    if type(before) is not type(after):
        return False
    if isinstance(before, Mapping):
        if not isinstance(after, Mapping) or len(before) != len(after):
            return False
        unmatched = list(after.items())
        for before_key, before_value in before.items():
            for index, (after_key, after_value) in enumerate(unmatched):
                if _same_value(before_key, after_key) and _same_value(before_value, after_value):
                    del unmatched[index]
                    break
            else:
                return False
        return not unmatched
    if isinstance(before, (list, tuple)):
        return isinstance(after, type(before)) and len(before) == len(after) and all(
            _same_value(before_item, after_item)
            for before_item, after_item in zip(before, after, strict=True)
        )
    return before == after


def _frontmatter_block(text: str) -> str | None:
    """Return a delimited frontmatter payload, or None when it is body text."""
    if text.startswith("---\r\n"):
        newline = "\r\n"
    elif text.startswith("---\n"):
        newline = "\n"
    else:
        return None
    content = text[len("---" + newline) :]
    closing = f"{newline}---{newline}"
    closing_index = content.find(closing)
    return None if closing_index == -1 else content[:closing_index]


def _yaml_key(node: ScalarNode) -> object:
    try:
        return yaml.safe_load(yaml.serialize(node))
    except yaml.YAMLError as exc:
        raise ExtractError(f"unparseable frontmatter key: {exc}") from exc


def _validate_mapping_keys(node: Node, *, top_level: bool) -> None:
    """Reject key collisions that Python's mapping construction would erase."""
    if not isinstance(node, MappingNode):
        return

    seen: list[object] = []
    fields: set[str] = set()
    for key_node, value_node in node.value:
        if not isinstance(key_node, ScalarNode):
            raise ExtractError("frontmatter mapping keys must be scalar")
        key = _yaml_key(key_node)
        for previous in seen:
            if key == previous:
                if type(key) is not type(previous):
                    raise ExtractError("frontmatter keys collide under Python equality")
                raise ExtractError("frontmatter contains a duplicate key")
        seen.append(key)
        if top_level:
            field = str(key)
            if field in fields:
                raise ExtractError("frontmatter keys collide when converted to field names")
            fields.add(field)
        _validate_mapping_keys(value_node, top_level=False)


def _field_map(frontmatter: dict, block: str | None) -> dict[str, object]:
    if block is not None:
        try:
            node = yaml.compose(block)
        except yaml.YAMLError as exc:
            raise ExtractError(f"unparseable frontmatter: {exc}") from exc
        if node is not None:
            _validate_mapping_keys(node, top_level=True)

    fields: dict[str, object] = {}
    for key, value in frontmatter.items():
        field = str(key)
        if field in fields:
            raise ExtractError("frontmatter keys collide when converted to field names")
        fields[field] = value
    return fields


def _frontmatter_template(block: str) -> tuple[tuple[tuple[str, str], ...], dict[str, str]]:
    """Keep source syntax, replacing only simple top-level scalar values."""
    template: list[tuple[str, str]] = []
    values: dict[str, str] = {}
    for line in block.splitlines(keepends=True):
        raw_line = line.rstrip("\r\n")
        if raw_line and not raw_line[0].isspace() and ":" in raw_line and "#" not in raw_line:
            raw_key, raw_value = raw_line.split(":", 1)
            if raw_key and raw_value.startswith(" "):
                try:
                    parsed = yaml.safe_load(f"{raw_key}: null\n")
                except yaml.YAMLError as exc:
                    raise ExtractError(f"unparseable frontmatter key: {exc}") from exc
                if isinstance(parsed, dict) and len(parsed) == 1:
                    key = str(next(iter(parsed)))
                    template.append(("field", key))
                    values[key] = raw_value
                    continue
        template.append(("raw", line))
    return tuple(template), values


def _has_unaccounted_syntax_change(
    before_block: str | None,
    after_block: str | None,
    changed_fields: set[str],
) -> bool:
    if before_block is None or after_block is None or before_block == after_block:
        return False

    before_template, before_values = _frontmatter_template(before_block)
    after_template, after_values = _frontmatter_template(after_block)
    before_fields = {value for kind, value in before_template if kind == "field"}
    after_fields = {value for kind, value in after_template if kind == "field"}
    added_or_removed = before_fields ^ after_fields
    before_shape = tuple(
        token
        for token in before_template
        if token[0] != "field" or token[1] not in added_or_removed
    )
    after_shape = tuple(
        token
        for token in after_template
        if token[0] != "field" or token[1] not in added_or_removed
    )
    if before_shape != after_shape:
        return True
    return any(
        before_values[field] != after_values[field] and field not in changed_fields
        for field in before_fields & after_fields
    )


def _changed_fields(before_text: str | None, after_text: str | None) -> tuple[str, ...]:
    """Return changed frontmatter keys and BODY_FIELD for a body change."""
    try:
        before_fm, before_body = (
            split_frontmatter(before_text) if before_text is not None else ({}, "")
        )
        after_fm, after_body = split_frontmatter(after_text) if after_text is not None else ({}, "")
    except yaml.YAMLError as exc:
        raise ExtractError(f"unparseable frontmatter: {exc}") from exc

    before_block = _frontmatter_block(before_text) if before_text is not None else None
    after_block = _frontmatter_block(after_text) if after_text is not None else None
    before = _field_map(before_fm, before_block)
    after = _field_map(after_fm, after_block)
    changed = {
        key
        for key in before.keys() | after.keys()
        if key not in before
        or key not in after
        or not _same_value(before.get(key, _MISSING), after.get(key, _MISSING))
    }
    if before_body != after_body:
        changed.add(BODY_FIELD)
    if _has_unaccounted_syntax_change(before_block, after_block, changed):
        changed.add(UNACCOUNTED_CHANGE_FIELD)
    return tuple(sorted(changed))


def _metadata_changes(repo_root: Path, base: str, head: str) -> dict[tuple[str, ChangeType], bool]:
    """Return the raw-diff mode-change bit for each path/status record."""
    raw = _git(repo_root, "diff", "--raw", "-z", "--no-renames", base, head)
    try:
        records = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractError(f"git raw diff emitted non-utf-8 data: {exc}") from exc
    fields = records.split("\0")
    if fields[-1] != "":
        raise ExtractError("git raw diff emitted an unterminated record")

    metadata: dict[tuple[str, ChangeType], bool] = {}
    fields_iter = iter(fields[:-1])
    for header in fields_iter:
        path = next(fields_iter, None)
        if path is None or not path:
            raise ExtractError("git raw diff emitted a record with no path")
        parts = header.split()
        if len(parts) != 5 or not parts[0].startswith(":"):
            raise ExtractError(f"malformed git raw diff record {header!r}")
        old_mode, new_mode = parts[0][1:], parts[1]
        status = _STATUS_TO_CHANGE_TYPE.get(parts[4])
        if not old_mode.isdigit() or not new_mode.isdigit() or status is None:
            raise ExtractError(f"malformed git raw diff record {header!r}")
        key = (path, status)
        if key in metadata:
            raise ExtractError(f"duplicate git raw diff record for {path!r}")
        metadata[key] = old_mode != new_mode
    return metadata


def extract_change_set(repo_root: Path, base: str, head: str) -> ChangeSet:
    """Diff `base` against `head` and describe every changed path.

    `--no-renames` makes a rename a deletion plus an addition, which the gate must
    decide independently.
    """
    base_commit = _require_commit(repo_root, base)
    head_commit = _require_commit(repo_root, head)

    raw = _git(
        repo_root, "diff", "--name-status", "-z", "--no-renames", base_commit, head_commit
    )
    metadata = _metadata_changes(repo_root, base_commit, head_commit)
    try:
        records = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractError(f"git diff emitted non-utf-8 status data: {exc}") from exc
    fields = records.split("\0")
    if fields[-1] != "":
        raise ExtractError("git diff emitted an unterminated name-status record")
    fields_iter = iter(fields[:-1])

    changes: list[PathChange] = []
    seen_metadata: set[tuple[str, ChangeType]] = set()
    for status in fields_iter:
        path = next(fields_iter, None)
        if path is None:
            raise ExtractError(f"git diff emitted a status {status!r} with no path")
        if not path:
            raise ExtractError(f"git diff emitted a status {status!r} with an empty path")
        change_type = _STATUS_TO_CHANGE_TYPE.get(status)
        if change_type is None:
            raise ExtractError(f"unhandled git diff status {status!r} for {path!r}")
        metadata_key = (path, change_type)
        if metadata_key not in metadata:
            raise ExtractError(f"name-status record for {path!r} is absent from the raw diff")
        seen_metadata.add(metadata_key)

        kind = entity_kind_for_path(path)
        if kind is None:
            changes.append(
                PathChange(path=path, change_type=change_type, entity_kind=None, fields=())
            )
            continue

        before = None if change_type is ChangeType.ADDED else _blob(repo_root, base_commit, path)
        after = None if change_type is ChangeType.DELETED else _blob(repo_root, head_commit, path)
        fields = set(_changed_fields(before, after))
        if change_type is ChangeType.MODIFIED and metadata[metadata_key]:
            fields.add(UNACCOUNTED_CHANGE_FIELD)
        changes.append(
            PathChange(
                path=path,
                change_type=change_type,
                entity_kind=kind,
                fields=tuple(sorted(fields)),
            )
        )

    if seen_metadata != set(metadata):
        raise ExtractError("raw diff records do not match name-status records")

    return ChangeSet(
        base_commit=base_commit,
        head_commit=head_commit,
        changes=tuple(sorted(changes, key=lambda change: change.path)),
    )
