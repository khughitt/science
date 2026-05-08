"""Validation helpers for typed blocker refs on tasks."""

from __future__ import annotations

import re
from pathlib import Path

from science_tool.entities import load_local_entity_ids

# Format: <kind>:<local-id> where kind is lowercase letters/digits/hyphens
# and local-id is anything non-empty without whitespace or @.
_TYPED_REF_RE = re.compile(r"^[a-z][a-z0-9-]*:[^@\s]+$")


def is_typed_ref(ref: str) -> bool:
    """Return True if `ref` matches the typed entity reference format <kind>:<local-id>."""
    return _TYPED_REF_RE.match(ref) is not None


class BlockerValidationError(ValueError):
    """Raised when a blocker reference fails validation."""


def validate_blocker_refs(
    project_root: Path,
    refs: list[str],
    *,
    force: bool = False,
) -> list[str]:
    """Validate and normalize a list of blocker refs.

    - Rejects refs not matching `^<kind>:<local-id>$` (always; --force does not bypass).
    - Rejects refs that don't resolve to a known local ProjectEntity, unless `force=True`.
    - Returns the (possibly normalized) ref list on success.
    - Raises `BlockerValidationError` with a concrete actionable message on failure.
    """
    for ref in refs:
        if not _TYPED_REF_RE.match(ref):
            raise BlockerValidationError(
                f"blocker {ref!r} must be typed: <kind>:<local-id> (e.g. dataset:foo, task:t007)"
            )

    if force:
        return list(refs)

    known = load_local_entity_ids(project_root)
    for ref in refs:
        if ref not in known:
            raise BlockerValidationError(
                f"unknown entity {ref}. Create the corresponding entity file first, or pass --force to record anyway."
            )
    return list(refs)
