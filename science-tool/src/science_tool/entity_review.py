"""Implementation of `entity review` command.

`entity review <id>` updates the review_state.last_reviewed (and optional
last_review_note) frontmatter on the named entity. It is the only command
in Phase 1 that mutates entity frontmatter from the freshness pipeline.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from science_tool.entities import EntityCommandError, find_entity


class ReviewError(Exception):
    pass


def review_entity(
    project_root: Path,
    entity_ref: str,
    *,
    note: str | None = None,
    today: date | None = None,
) -> Path:
    """Set review_state.last_reviewed = today on the entity's frontmatter.

    Preserves any existing review_state fields (review_horizon_days,
    last_review_note when no new note is passed) by doing a YAML
    round-trip: parse -> mutate the dict -> re-dump.

    Returns the entity's file path. Raises ReviewError on lookup failure.
    """
    today = today or date.today()
    try:
        location = find_entity(project_root, entity_ref)
    except EntityCommandError as exc:
        raise ReviewError(str(exc)) from exc

    path = project_root / location.rel_path
    text = path.read_text()
    new_text = _upsert_review_state(text, last_reviewed=today, note=note)
    if new_text != text:
        path.write_text(new_text)
    return path


def _upsert_review_state(text: str, *, last_reviewed: date, note: str | None) -> str:
    """Update review_state in YAML frontmatter, preserving sibling fields.

    YAML round-trip: split frontmatter from body on the `---` delimiters,
    parse the frontmatter to a dict, mutate `review_state` in place
    (creating it if missing), re-dump with `yaml.safe_dump`. This preserves
    `review_horizon_days` and any pre-existing `last_review_note` when the
    caller did not pass a new note.

    Note semantics: passing `note=None` leaves any existing
    `last_review_note` untouched. Passing `note=""` clears it.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != "---":
        raise ReviewError("entity file lacks YAML frontmatter")

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\n") == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ReviewError("entity file frontmatter is unterminated")

    fm_text = "".join(lines[1:end_idx])
    body_text = "".join(lines[end_idx + 1:])

    fm = yaml.safe_load(fm_text) or {}
    if not isinstance(fm, dict):
        raise ReviewError("frontmatter is not a YAML mapping")

    rs = fm.get("review_state")
    if not isinstance(rs, dict):
        rs = {}
    rs["last_reviewed"] = last_reviewed.isoformat()
    if note is not None:
        if note == "":
            rs.pop("last_review_note", None)
        else:
            rs["last_review_note"] = note
    fm["review_state"] = rs

    new_fm_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=False)
    return f"---\n{new_fm_text}---\n{body_text}"
