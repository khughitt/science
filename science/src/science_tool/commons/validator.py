"""`science commons validate` driver: walk store + run EntityValidator.

Reads the filesystem directly (does not consult the registry, which may be
stale or absent).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.errors import CommonsEntityError
from science_tool.entities import valid_statuses


@dataclass(frozen=True)
class CommonsStatusWarning:
    """A commons record whose `status` is outside its kind's vocabulary.

    A WARNING, never an error: the commons dataset schema accepts any string
    status (`status` is a bare `{"type": "string"}`), so a value like
    `exploratory` passes schema validation. The kind vocabulary is uncertified
    for the commons store, so this advises rather than gates (fb-2026-07-12-007).
    """

    canonical_id: str
    path: Path
    message: str


@dataclass(frozen=True)
class ValidationReport:
    checked: int
    errors: list[CommonsEntityError]
    warnings: list[CommonsStatusWarning] = field(default_factory=list)


class CommonsValidator:
    """Walk the commons store and surface EntityValidator errors."""

    def __init__(self, adapter: CommonsEntityAdapter) -> None:
        self._adapter = adapter

    def validate(self, *, type: str | None = None, slug: str | None = None) -> ValidationReport:
        checked = 0
        errors: list[CommonsEntityError] = []
        warnings: list[CommonsStatusWarning] = []
        for item in self._adapter.scan():
            if isinstance(item, CommonsEntityError):
                if not self._matches_error(item, type=type, slug=slug):
                    continue
                checked += 1
                errors.append(item)
                continue
            if not self._matches_record(item, type=type, slug=slug):
                continue
            checked += 1
            status_warning = self._status_warning(item)
            if status_warning is not None:
                warnings.append(status_warning)
        return ValidationReport(checked=checked, errors=errors, warnings=warnings)

    @staticmethod
    def _status_warning(record: CommonsEntityRecord) -> CommonsStatusWarning | None:
        """The status-vocabulary warning for `record`, or None if it conforms.

        `status_vocabulary` (project validate) walks only `<root>/entities`, so it
        never reaches commons records at `papers/<key>.md` / `datasets/<slug>/entity.md`.
        This is that check's commons counterpart, over the kind vocabulary shared
        with `edit_entity` (`valid_statuses`).
        """
        status = record.frontmatter.get("status")
        kind = record.frontmatter.get("kind")
        if not isinstance(status, str) or not status or not isinstance(kind, str) or not kind:
            return None
        try:
            allowed = valid_statuses(kind)
        except KeyError:
            return None  # an unregistered kind is a schema concern, not this one
        if allowed is None or status in allowed:
            return None  # None = open status set (any value legal)
        return CommonsStatusWarning(
            canonical_id=record.canonical_id,
            path=record.body_path,
            message=(
                f"status {status!r} is not in the declared vocabulary for kind {kind!r} "
                f"({', '.join(sorted(allowed))})."
            ),
        )

    @staticmethod
    def _matches_record(
        record: CommonsEntityRecord, *, type: str | None, slug: str | None
    ) -> bool:
        if type is not None and record.type != type:
            return False
        if slug is not None and record.slug != slug:
            return False
        return True

    @staticmethod
    def _matches_error(
        err: CommonsEntityError, *, type: str | None, slug: str | None
    ) -> bool:
        if type is None and slug is None:
            return True
        # An error without a canonical_id can't be matched against a type/slug
        # filter, so it is treated as non-matching. In practice the adapter's
        # _build always sets canonical_id on the errors it yields.
        canonical = err.canonical_id or ""
        err_type, _, err_slug = canonical.partition(":")
        if type is not None and err_type != type:
            return False
        if slug is not None and err_slug != slug:
            return False
        return True
