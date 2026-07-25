"""The closed vocabulary of skill-coverage enrollment domains and statuses.

This module is the SINGLE authority on which domains a project may enroll in for skill-coverage
analysis AND on the enrollment-status values. `science_tool`'s project config imports these and never
re-declares them: a status or domain that is legal here and nowhere else is what "one registered
authority" means. Adding a domain is a change here (and, if it reads the generation-3 capability
shape, in GENERATION_3_DOMAINS); the two status values live only in EnrollmentStatus.
"""

from __future__ import annotations

from enum import StrEnum

from science_model.skill_coverage.overlay import (
    Companion,
    LeafSkill,
    RouterSkill,
    SkillOverlay,
    SkillOverlayError,
    build_skill_overlay,
)


class EnrollmentStatus(StrEnum):
    """The two authored enrollment statuses. `undeclared` is NOT here: it is an ABSENCE state, never
    an authored value, so it is resolved by the reader, not selected in science.yaml."""

    ENROLLED = "enrolled"
    OUT_OF_DOMAIN = "out-of-domain"


# Enrollable domain keys. Closed: a `skill_coverage.domains` key outside this set is a hard config
# error, never a silently-preserved unknown. v1 ships exactly the molecular-measurement domain.
DOMAIN_KEYS: frozenset[str] = frozenset({"molecular-measurement"})

# The enrollment status VALUES, DERIVED from EnrollmentStatus so the set can never drift from the
# type. Consumers that need the values as a set read this; consumers that validate a field type read
# EnrollmentStatus directly.
ENROLLMENT_STATUSES: frozenset[str] = frozenset(status.value for status in EnrollmentStatus)

# Domains whose coverage analysis reads the generation-3 capability shape. Enrolling one of these
# requires the project to be pinned `entity_schema_version: 3`; the cross-field rule that enforces
# this lives with the config that also owns the pin (science_tool ProjectConfig). Subset of
# DOMAIN_KEYS by construction.
GENERATION_3_DOMAINS: frozenset[str] = frozenset({"molecular-measurement"})

__all__ = [
    "Companion",
    "DOMAIN_KEYS",
    "ENROLLMENT_STATUSES",
    "EnrollmentStatus",
    "GENERATION_3_DOMAINS",
    "LeafSkill",
    "RouterSkill",
    "SkillOverlay",
    "SkillOverlayError",
    "build_skill_overlay",
]
