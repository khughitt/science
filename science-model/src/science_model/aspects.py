"""Shared aspect vocabulary, resolution, validation, and filtering helpers.

Entity-level `aspects:` uses the same vocabulary as project-level `aspects:` in
science.yaml. This module is the single source of truth for that vocabulary
and for the resolution/filter rules; commands consume it rather than
reimplementing aspect logic.
"""
from __future__ import annotations

KNOWN_ASPECTS: frozenset[str] = frozenset(
    {
        "causal-modeling",
        "hypothesis-testing",
        "computational-analysis",
        "software-development",
    }
)

SOFTWARE_ASPECT: str = "software-development"
