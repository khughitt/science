"""Authoritative enrollment statuses for skill-coverage analysis.

``undeclared`` is intentionally absent: it is a reader-resolved absence state,
not an authored value in project configuration.
"""

from __future__ import annotations

from enum import StrEnum


class EnrollmentStatus(StrEnum):
    """The authored enrollment statuses."""

    ENROLLED = "enrolled"
    OUT_OF_DOMAIN = "out-of-domain"


ENROLLMENT_STATUSES: frozenset[str] = frozenset(
    status.value for status in EnrollmentStatus
)
