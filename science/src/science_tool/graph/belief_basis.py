"""Belief-basis capture and comparison — the observable the autonomy semantic gate compares.

The basis is deliberately the *inputs* to belief, not the aggregated verdict: a run
whose evidence units change but happen to cancel leaves the ordinal magnitude intact
and must still be detected.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from science_tool.graph.belief import EvidenceUnit


def unit_key(unit: EvidenceUnit) -> str:
    """Canonical, comparable key for one evidence unit.

    Derived from `asdict` so a NEW field on EvidenceUnit enters the key automatically.
    Never rewrite this against an explicit field list: an unrecognized belief input
    must change the basis rather than be silently dropped from it.

    No `default=` fallback: a future field whose type is not JSON-native must raise
    here rather than be coerced to a string, which could collapse distinct values.
    """
    return json.dumps(asdict(unit), sort_keys=True)
