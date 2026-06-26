"""Validation helpers for typed blocker refs on tasks."""

from __future__ import annotations

import re
from pathlib import Path

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
                "blocker "
                f"{ref!r} must be typed: <kind>:<local-id> or <peer>:<kind>:<local-id> "
                "(e.g. dataset:foo, task:t007, meta:task:t007)"
            )

    if force:
        return list(refs)

    from science_tool.tasks_readiness import make_project_entity_lookup

    try:
        lookup = make_project_entity_lookup(project_root)
    except ValueError as exc:
        raise BlockerValidationError(str(exc)) from exc
    for ref in refs:
        if lookup(ref) is None:
            raise BlockerValidationError(
                f"unknown entity {ref}. Create the corresponding entity file first, or pass --force to record anyway."
            )
    return list(refs)
