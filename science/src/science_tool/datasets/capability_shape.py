"""The single canonical capability shape parser — shared by validate + the matcher."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

_DP_PREFIX = "data-product:"
_ALLOWED_GEN3_KEYS = {"data_product", "qualifiers"}
_DP_SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")


@dataclass(frozen=True)
class Capability:
    data_product: str
    qualifiers: dict[str, str] = field(default_factory=dict)


def _valid_dp(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith(_DP_PREFIX):
        return False
    return _DP_SLUG.fullmatch(value[len(_DP_PREFIX):]) is not None


def _valid_qualifiers(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    for key, raw in value.items():
        if not isinstance(key, str) or not key.strip():
            return False
        if not isinstance(raw, str) or not raw.strip():
            return False
    return True


def _gen3_entry_ok(entry: object) -> bool:
    if not isinstance(entry, Mapping) or not entry:
        return False
    if set(entry.keys()) - _ALLOWED_GEN3_KEYS:
        return False
    if not _valid_dp(entry.get("data_product")):
        return False
    if "qualifiers" in entry and not _valid_qualifiers(entry["qualifiers"]):
        return False
    return True


def gen3_shape_issue(value: object) -> str | None:
    if value is None or value == []:
        return "missing"
    if not isinstance(value, list):
        return "malformed"
    for entry in value:
        if not _gen3_entry_ok(entry):
            return "malformed"
    return None


def parse_gen3_capabilities(value: object) -> list[Capability]:
    """Parse a gen-3 capability list. Entries failing the full gen-3 shape are skipped."""
    if not isinstance(value, list):
        return []
    out: list[Capability] = []
    for entry in value:
        if not _gen3_entry_ok(entry):
            continue
        quals_raw = entry.get("qualifiers", {})
        quals = {k.strip(): v.strip() for k, v in quals_raw.items()}
        out.append(Capability(data_product=str(entry["data_product"]), qualifiers=quals))
    return out


def legacy_map_shape_issue(value: object) -> str | None:
    if value is None or value == []:
        return "missing"
    if not isinstance(value, list):
        return "malformed"
    for entry in value:
        if not isinstance(entry, Mapping) or not entry:
            return "malformed"
        for key, raw in entry.items():
            if not isinstance(key, str) or not key.strip():
                return "malformed"
            if not isinstance(raw, str) or not raw.strip():
                return "malformed"
    return None


def capability_shape_issue(value: object, *, generation: int = 2) -> str | None:
    return gen3_shape_issue(value) if generation >= 3 else legacy_map_shape_issue(value)
