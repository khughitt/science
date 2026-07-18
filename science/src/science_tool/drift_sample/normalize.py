"""Predeclared claim normalization (design §6.2a). FIXED BEFORE THE DRAW.

`mismatch = adjudicated != claimed` is ill-defined against an illegal claim.
21 of natural-systems' 109 plans claim an illegal status and multiple-myeloma
claims zero, so comparing raw would make NS look drifty from S4's vocabulary
problem rather than its own drift.

Upstream-prescribed where upstream has spoken; refuses to invent where it has
not. `approved` / `draft-for-review` / `ready-with-caveats` / `not-ready` are
S4's open question -- mapping them here would decide S4 silently inside S1's
evidence and would move S1's answer.
"""

from __future__ import annotations

LEGAL: frozenset[str] = frozenset(
    {"draft", "active", "complete", "superseded", "retired", "archived"}
)

CLAIM_MAP: dict[str, str] = {
    **{value: value for value in LEGAL},
    "proposed": "draft",      # upstream-prescribed: core.py calls it drift toward `draft`
    "design": "draft",        # lifecycle position
    "implemented": "complete",
    "completed": "complete",
    "in-progress": "active",
    "current": "active",
    "agreed": "active",
}


def normalize_claim(claimed: str) -> str | None:
    """Return the legal status this claim means, or None if unmappable."""
    return CLAIM_MAP.get(claimed.strip().lower())
