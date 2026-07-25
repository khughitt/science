"""Build a `ChangeSet` from a recorded `base..head` commit range.

The range is two-dot (tree to tree) by construction. A merge-base range moves under
rebase and under integration-branch advancement, which is exactly the baseline
instability design §6 rejects -- so `...` must never appear here.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from science_model.frontmatter import split_frontmatter

from science_tool.autonomy.changes import (
    BODY_FIELD,
    ChangeSet,
    ChangeType,
    PathChange,
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
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(repo_root), *args], capture_output=True
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise ExtractError(f"git {' '.join(args)} failed in {repo_root}: {message}")
    return result.stdout


def _require_commit(repo_root: Path, rev: str) -> str:
    return _git(repo_root, "rev-parse", "--verify", f"{rev}^{{commit}}").decode().strip()


def _blob(repo_root: Path, commit: str, path: str) -> str:
    """Return a UTF-8 file blob at a commit, failing closed on unreadable input."""
    raw = _git(repo_root, "show", f"{commit}:{path}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractError(f"{path} at {commit} is not utf-8 text: {exc}") from exc


_MISSING = object()


def _changed_fields(before_text: str | None, after_text: str | None) -> tuple[str, ...]:
    """Return changed frontmatter keys and BODY_FIELD for a body change."""
    try:
        before_fm, before_body = (
            split_frontmatter(before_text) if before_text is not None else ({}, "")
        )
        after_fm, after_body = split_frontmatter(after_text) if after_text is not None else ({}, "")
    except yaml.YAMLError as exc:
        raise ExtractError(f"unparseable frontmatter: {exc}") from exc

    before = {str(key): value for key, value in before_fm.items()}
    after = {str(key): value for key, value in after_fm.items()}
    changed = {
        key
        for key in before.keys() | after.keys()
        if before.get(key, _MISSING) != after.get(key, _MISSING)
    }
    if before_body != after_body:
        changed.add(BODY_FIELD)
    return tuple(sorted(changed))


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
    try:
        records = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractError(f"git diff emitted non-utf-8 status data: {exc}") from exc
    fields = records.split("\0")
    if fields[-1] != "":
        raise ExtractError("git diff emitted an unterminated name-status record")
    fields_iter = iter(fields[:-1])

    changes: list[PathChange] = []
    for status in fields_iter:
        path = next(fields_iter, None)
        if path is None:
            raise ExtractError(f"git diff emitted a status {status!r} with no path")
        if not path:
            raise ExtractError(f"git diff emitted a status {status!r} with an empty path")
        change_type = _STATUS_TO_CHANGE_TYPE.get(status)
        if change_type is None:
            raise ExtractError(f"unhandled git diff status {status!r} for {path!r}")

        kind = entity_kind_for_path(path)
        if kind is None:
            changes.append(
                PathChange(path=path, change_type=change_type, entity_kind=None, fields=())
            )
            continue

        before = None if change_type is ChangeType.ADDED else _blob(repo_root, base_commit, path)
        after = None if change_type is ChangeType.DELETED else _blob(repo_root, head_commit, path)
        changes.append(
            PathChange(
                path=path,
                change_type=change_type,
                entity_kind=kind,
                fields=_changed_fields(before, after),
            )
        )

    return ChangeSet(
        base_commit=base_commit,
        head_commit=head_commit,
        changes=tuple(sorted(changes, key=lambda change: change.path)),
    )
