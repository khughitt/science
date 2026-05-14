"""`science commons validate` driver: walk store + run EntityValidator.

Reads the filesystem directly (does not consult the registry, which may be
stale or absent).
"""

from __future__ import annotations

from dataclasses import dataclass

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.errors import CommonsEntityError


@dataclass(frozen=True)
class ValidationReport:
    checked: int
    errors: list[CommonsEntityError]


class CommonsValidator:
    """Walk the commons store and surface EntityValidator errors."""

    def __init__(self, adapter: CommonsEntityAdapter) -> None:
        self._adapter = adapter

    def validate(self, *, type: str | None = None, slug: str | None = None) -> ValidationReport:
        checked = 0
        errors: list[CommonsEntityError] = []
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
        return ValidationReport(checked=checked, errors=errors)

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
        canonical = err.canonical_id or ""
        err_type, _, err_slug = canonical.partition(":")
        if type is not None and err_type != type:
            return False
        if slug is not None and err_slug != slug:
            return False
        return True
