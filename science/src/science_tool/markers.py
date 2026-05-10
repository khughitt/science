"""Annotation-token scanner — single source of truth for marker scanning.

Used by both `science refs check` and `validate.sh` (via
`science markers scan --format json`). See
`docs/conventions/annotation-tokens.md` for the vocabulary and severity rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Canonical token names, ordered for stable display.
TOKENS: tuple[str, ...] = ("UNVERIFIED", "MISSING_CITATION", "SPECULATION", "INACCESSIBLE")

# Default severity per token. `--strict` promotes any "info" entry to "warn".
DEFAULT_SEVERITY: dict[str, str] = {
    "UNVERIFIED": "warn",
    "MISSING_CITATION": "warn",
    "SPECULATION": "info",
    "INACCESSIBLE": "info",
}

# Legacy spellings recognized during the deprecation window. Maps the *literal
# inner text* (without brackets) to the canonical token name.
LEGACY_ALIASES: dict[str, str] = {"NEEDS CITATION": "MISSING_CITATION"}


@dataclass(frozen=True)
class MarkerHit:
    """One marker occurrence found by the scanner."""

    file: Path
    line: int
    token: str  # one of TOKENS
    severity: str  # "warn" | "info"
    in_documentation: bool  # True if backticked or inside a fenced code block
    legacy: bool  # True if the source spelling was a legacy alias


def severity_for(token: str, *, strict: bool) -> str:
    """Resolve effective severity for a canonical token under the strict flag."""
    base = DEFAULT_SEVERITY[token]
    if strict and base == "info":
        return "warn"
    return base
