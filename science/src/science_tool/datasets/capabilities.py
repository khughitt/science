"""Capability-fit helpers for dataset coverage credit."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


CapabilitySet = dict[str, str]


@dataclass(frozen=True)
class CapabilityFit:
    compatible: bool
    reason: str
    required: list[CapabilitySet]
    provided: list[CapabilitySet]


def capability_sets_from(value: object) -> list[CapabilitySet]:
    """Normalize frontmatter capability sets.

    The first slice accepts a list of mappings with non-empty string keys and
    values. Malformed entries are ignored so callers can conservatively avoid
    coverage credit without crashing command output.
    """
    if not isinstance(value, list):
        return []
    sets: list[CapabilitySet] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        normalized: CapabilitySet = {}
        for key, raw in entry.items():
            if not isinstance(key, str) or not isinstance(raw, str):
                continue
            clean_key = key.strip()
            clean_value = raw.strip()
            if clean_key and clean_value:
                normalized[clean_key] = clean_value
        if normalized:
            sets.append(normalized)
    return sets


def compatible(required_sets: list[CapabilitySet], provided_sets: list[CapabilitySet]) -> bool:
    """Return whether any provided set satisfies any required set."""
    return any(_satisfies(required, provided) for required in required_sets for provided in provided_sets)


def capability_fit(required: object, provided: object) -> CapabilityFit:
    """Evaluate whether provided dataset capabilities satisfy target requirements."""
    required_sets = capability_sets_from(required)
    provided_sets = capability_sets_from(provided)
    if not required_sets:
        return CapabilityFit(False, "missing-required-capabilities", required_sets, provided_sets)
    if not provided_sets:
        return CapabilityFit(False, "missing-provided-capabilities", required_sets, provided_sets)
    if compatible(required_sets, provided_sets):
        return CapabilityFit(True, "compatible", required_sets, provided_sets)
    return CapabilityFit(False, "capability-mismatch", required_sets, provided_sets)


def _satisfies(required: CapabilitySet, provided: CapabilitySet) -> bool:
    return all(provided.get(key) == value for key, value in required.items())
