"""Curated, SPDX-aligned license vocabulary for dataset entities.

Membership is exact (case-sensitive); `suggest()` is fuzzy and only used to
build "did you mean" hints. Deliberately a single small module so the allow-list
is easy to extend. Per-project extensibility is a future enhancement.
"""

from __future__ import annotations

import difflib

KNOWN_LICENSES: frozenset[str] = frozenset(
    {
        "CC-BY-4.0",
        "CC-BY-SA-4.0",
        "CC-BY-ND-4.0",
        "CC-BY-NC-4.0",
        "CC-BY-NC-SA-4.0",
        "CC-BY-NC-ND-4.0",
        "CC0-1.0",
        "ODbL-1.0",
        "ODC-BY-1.0",
        "PDDL-1.0",
        "MIT",
        "Apache-2.0",
        "BSD-3-Clause",
        "GPL-3.0-only",
        "LGPL-3.0-only",
    }
)

# Honest non-license states. They satisfy presence (clear the missing-license
# warning) without being treated as a real license.
LICENSE_SENTINELS: frozenset[str] = frozenset({"unknown", "proprietary", "custom"})

_CASE_INSENSITIVE = {lic.lower(): lic for lic in KNOWN_LICENSES}


def is_recognized(value: str) -> bool:
    """True iff `value` is exactly a known license id or a sentinel."""
    return value in KNOWN_LICENSES or value in LICENSE_SENTINELS


def suggest(value: str) -> str | None:
    """Closest known license id for a "did you mean" hint, or None.

    Tries a case-insensitive / separator-normalized exact match first, then a
    fuzzy match against the known ids. Never returns a sentinel.
    """
    candidate = value.strip()
    if not candidate:
        return None
    normalized = candidate.lower().replace("_", "-").replace(" ", "-")
    if normalized in _CASE_INSENSITIVE:
        return _CASE_INSENSITIVE[normalized]
    close = difflib.get_close_matches(candidate, list(KNOWN_LICENSES), n=1, cutoff=0.6)
    return close[0] if close else None
