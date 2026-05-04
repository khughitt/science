"""Implementation of `entity review` and `entity needs-review` commands.

`entity review <id>` updates the review_state.last_reviewed (and optional
last_review_note) frontmatter on the named entity. It is the only command
in Phase 1 that mutates entity frontmatter from the freshness pipeline.

Reuses `science_tool.entities` for frontmatter parsing, rendering, and
atomic writes — those are the canonical helpers used by `edit_entity` and
`append_entity_note`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from science_tool.entities import (
    EntityCommandError,
    _atomic_replace_text,
    _render_markdown,
    find_entity,
)


class ReviewError(Exception):
    pass


def review_entity(
    project_root: Path,
    entity_ref: str,
    *,
    note: str | None = None,
    today: date | None = None,
) -> tuple[Path, bool]:
    """Set review_state.last_reviewed = today on the entity's frontmatter.

    Preserves any existing review_state fields. Note semantics: `note=None`
    keeps any existing `last_review_note`; `note=""` clears it; a non-empty
    string replaces it.

    Returns (path, changed) — `changed` is True iff the file was rewritten.
    Raises ReviewError on lookup failure.
    """
    today = today or date.today()
    try:
        location = find_entity(project_root, entity_ref)
    except EntityCommandError as exc:
        raise ReviewError(str(exc)) from exc

    path = project_root / location.rel_path
    frontmatter = dict(location.frontmatter)

    rs_raw = frontmatter.get("review_state")
    rs: dict = dict(rs_raw) if isinstance(rs_raw, dict) else {}
    rs["last_reviewed"] = today.isoformat()
    if note is not None:
        if note == "":
            rs.pop("last_review_note", None)
        else:
            rs["last_review_note"] = note
    frontmatter["review_state"] = rs

    new_text = _render_markdown(frontmatter, location.body)
    old_text = path.read_text()
    if new_text == old_text:
        return path, False
    _atomic_replace_text(path, new_text)
    return path, True
