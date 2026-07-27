"""Shared predicates for determining whether a pre-registration is frozen."""

from __future__ import annotations

from typing import Any


# The obligation attaches once the document is frozen, not while it is drafted.
_FROZEN_STATUSES = frozenset({"committed", "amended"})


def frozen_because(frontmatter: dict[str, Any]) -> str | None:
    """Why this pre-registration counts as frozen, or None if it does not.

    `status` is the primary signal, but it is not the only sound one, and on
    its own it under-reports. `default_status` for this kind is `active`
    (profiles/core.py) while `templates/pre-registration.md` displays
    `status: "committed"`, so a tool-created pre-registration lands on `active`
    and stays there unless the author edits it at sign-off. natural-systems had
    7 of 34 in exactly that state, two of them with amendment records and a
    drawn null (fb-2026-07-26-019).

    A non-empty `amendments:` list is therefore read as frozen too. That is a
    sufficient condition, not a heuristic: amending presupposes having
    committed, so there is no state in which an unfrozen document legitimately
    carries one. `commands/pre-register.md` prescribes the field for exactly
    this purpose. A `committed:` DATE is deliberately NOT read -- the template
    emits it unconditionally, so it is present on every pre-registration in
    practice (34 of 34 in the surveyed project) and discriminates nothing.
    """
    if str(frontmatter.get("status", "")) in _FROZEN_STATUSES:
        return f"status is {frontmatter.get('status')!r}"
    amendments = frontmatter.get("amendments")
    if isinstance(amendments, list) and amendments:
        plural = "s" if len(amendments) != 1 else ""
        return f"it records {len(amendments)} amendment{plural}, which presupposes a commitment"
    return None
