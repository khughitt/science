"""Capability-fit helpers for dataset coverage credit."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from science_model.data_products import DataProductCatalog
from science_tool.datasets.capability_shape import Capability, parse_gen3_capabilities


CapabilitySet = dict[str, str]


@dataclass(frozen=True)
class CapabilityFit:
    compatible: bool
    reason: str
    required: list[dict]
    provided: list[dict]


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


def capability_fit(
    required: object,
    provided: object,
    *,
    generation: int,
    catalog: DataProductCatalog | None = None,
) -> CapabilityFit:
    """Evaluate whether provided dataset capabilities satisfy target requirements.

    gen ≤ 2 uses the legacy string-map subset matcher; gen 3 parses both sides
    into `Capability` (data-product + qualifiers) and matches via catalog descent.
    """
    if generation >= 3:
        if catalog is None:
            raise ValueError("gen-3 capability_fit requires a catalog")
        return _capability_fit_gen3(required, provided, catalog)
    return _capability_fit_legacy(required, provided)


def _capability_fit_legacy(required: object, provided: object) -> CapabilityFit:
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


def _capability_fit_gen3(required: object, provided: object, catalog: DataProductCatalog) -> CapabilityFit:
    req = parse_gen3_capabilities(required)
    prov = parse_gen3_capabilities(provided)
    req_out = [{"data_product": c.data_product, "qualifiers": dict(c.qualifiers)} for c in req]
    prov_out = [{"data_product": c.data_product, "qualifiers": dict(c.qualifiers)} for c in prov]
    if not req:
        return CapabilityFit(False, "missing-required-capabilities", req_out, prov_out)
    if not prov:
        return CapabilityFit(False, "missing-provided-capabilities", req_out, prov_out)
    if any(_gen3_satisfies(r, p, catalog) for r in req for p in prov):
        return CapabilityFit(True, "compatible", req_out, prov_out)
    return CapabilityFit(False, "capability-mismatch", req_out, prov_out)


def _gen3_satisfies(required: Capability, provided: Capability, catalog: DataProductCatalog) -> bool:
    if not catalog.descends(provided.data_product, required.data_product):
        return False
    return all(provided.qualifiers.get(k) == v for k, v in required.qualifiers.items())
