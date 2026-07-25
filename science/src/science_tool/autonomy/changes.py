"""The change set the path gate decides over, and how a path maps to an entity kind."""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict
from science_model.profiles.core import CORE_PROFILE

#: Body prose is gated as a pseudo-field so it is denied by default exactly like any
#: frontmatter field. It is named for `Entity.content`, which is what it becomes.
BODY_FIELD = "content"


class ChangeType(StrEnum):
    MODIFIED = "modified"
    ADDED = "added"
    DELETED = "deleted"


class PathChange(BaseModel):
    """One repository path the run touched.

    `entity_kind` is derived from the PATH, never from the file's own `kind:`
    frontmatter -- an actor that could choose its own kind could choose the most
    permissive allowlist. `fields` is empty for non-entity paths, whose denial is
    decided by path alone.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    change_type: ChangeType
    entity_kind: str | None
    fields: tuple[str, ...]


class ChangeSet(BaseModel):
    """Everything that changed between two commits, in deterministic path order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_commit: str
    head_commit: str
    changes: tuple[PathChange, ...]


#: kind -> home, derived from CORE_PROFILE at import time.
#:
#: `science_tool.entities` is NOT used: importing it as the first `science_tool` module
#: fails deterministically through `commons/validator.py` (a real cycle on `main`).
#: Reading CORE_PROFILE instead means project-LOCAL kinds are never classified, so their
#: files return None and are denied. That is safe by construction -- a local kind has no
#: FIELD_ALLOWLIST entry, so classifying it could never have allowed anything.
_CORE_HOMES: tuple[tuple[str, PurePosixPath], ...] = tuple(
    sorted(
        ((kind.name, PurePosixPath(kind.home)) for kind in CORE_PROFILE.entity_kinds if kind.home),
        # Longest root first, so a nested home wins over a parent that prefixes it.
        key=lambda item: len(str(item[1])),
        reverse=True,
    )
)


def entity_kind_for_path(rel_path: str) -> str | None:
    """The core kind that owns `rel_path`, or None when it is not a core entity file.

    None means "unclassified", which the gate reads as denied. Every non-entity path,
    every project-local kind, every archive-tier path, and every non-markdown file
    lands here.
    """
    candidate = PurePosixPath(rel_path)
    if any(segment.startswith("_") for segment in candidate.parts):
        return None  # archive tier -- unclassified, therefore denied

    for kind, root in _CORE_HOMES:
        if root.suffix:  # singleton home: the home IS the file
            if candidate == root:
                return kind
            continue
        if candidate.parent == root and candidate.suffix == ".md":
            return kind
    return None
